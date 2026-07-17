from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from backend.ai_service import (
    MockAIAnalyzer,
    analyze_reconciliation_candidates,
)
from backend.evaluator import (
    ReconciliationEvaluationError,
    evaluate_reconciliation,
)
from backend.groq_analyzer import (
    GroqAnalysisError,
    GroqAnalyzer,
)
from backend.matcher import (
    match_exact_references,
    match_with_fallbacks,
)
from backend.validators import CSVValidationError, validate_csv


app = FastAPI(
    title="LedgerLens AI API",
    description=(
        "Backend API for validating financial data, matching invoices, "
        "payments and bank transactions, and evaluating reconciliation quality."
    ),
    version="0.7.0",
)


async def _read_validated_csv(
    file: UploadFile,
    dataset_type: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Read, validate and convert an uploaded LedgerLens CSV file.
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The {dataset_type} file must have a filename.",
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The {dataset_type} file must be a CSV file.",
        )

    content = await file.read()

    try:
        validation_result = validate_csv(
            content=content,
            dataset_type=dataset_type,
        )
    except CSVValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{dataset_type}: {error}",
        ) from error

    dataframe = pd.read_csv(
        BytesIO(content),
        dtype=str,
    )

    return dataframe, {
        "filename": file.filename,
        **validation_result,
    }


async def _read_expected_matches_csv(
    file: UploadFile,
) -> pd.DataFrame:
    """
    Read the labelled expected-matches CSV used for evaluation.
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The expected-matches file must have a filename.",
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The expected-matches file must be a CSV file.",
        )

    content = await file.read()

    if not content or not content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The expected-matches CSV file is empty.",
        )

    try:
        dataframe = pd.read_csv(
            BytesIO(content),
            dtype=str,
        )
    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "The expected-matches file could not be decoded. "
                "Upload a UTF-8 CSV file."
            ),
        ) from error
    except pd.errors.EmptyDataError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The expected-matches file contains no readable data.",
        ) from error
    except pd.errors.ParserError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The expected-matches CSV structure is invalid.",
        ) from error

    return dataframe


@app.get("/", tags=["System"])
async def root() -> dict[str, str]:
    """Return basic information about the LedgerLens AI API."""

    return {
        "service": "LedgerLens AI API",
        "version": "0.7.0",
        "status": "running",
        "documentation": "/docs",
    }


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Confirm that the backend service is available."""

    return {
        "status": "healthy",
        "service": "ledgerlens-ai-backend",
    }


@app.post("/validate/{dataset_type}", tags=["Validation"])
async def validate_uploaded_csv(
    dataset_type: str,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    Validate one uploaded LedgerLens CSV dataset.

    Supported dataset types:

    - invoices
    - payments
    - bank_transactions
    """

    try:
        _, validation_result = await _read_validated_csv(
            file=file,
            dataset_type=dataset_type,
        )

        return validation_result
    finally:
        await file.close()


@app.post("/reconcile/exact", tags=["Reconciliation"])
async def reconcile_exact_references(
    invoices_file: UploadFile = File(
        ...,
        description="Invoice CSV dataset.",
    ),
    payments_file: UploadFile = File(
        ...,
        description="Payment CSV dataset.",
    ),
    bank_transactions_file: UploadFile = File(
        ...,
        description="Bank transaction CSV dataset.",
    ),
) -> dict[str, Any]:
    """
    Reconcile records using exact references.
    """

    try:
        invoices, invoices_validation = await _read_validated_csv(
            file=invoices_file,
            dataset_type="invoices",
        )

        payments, payments_validation = await _read_validated_csv(
            file=payments_file,
            dataset_type="payments",
        )

        bank_transactions, bank_validation = await _read_validated_csv(
            file=bank_transactions_file,
            dataset_type="bank_transactions",
        )

        matching_result = match_exact_references(
            invoices=invoices,
            payments=payments,
            bank_transactions=bank_transactions,
        )

        return {
            "reconciliation_type": "deterministic_exact_reference",
            "source_validation": {
                "invoices": invoices_validation,
                "payments": payments_validation,
                "bank_transactions": bank_validation,
            },
            **matching_result,
        }
    finally:
        await invoices_file.close()
        await payments_file.close()
        await bank_transactions_file.close()


@app.post("/reconcile/fallback", tags=["Reconciliation"])
async def reconcile_with_fallback_rules(
    invoices_file: UploadFile = File(
        ...,
        description="Invoice CSV dataset.",
    ),
    payments_file: UploadFile = File(
        ...,
        description="Payment CSV dataset.",
    ),
    bank_transactions_file: UploadFile = File(
        ...,
        description="Bank transaction CSV dataset.",
    ),
) -> dict[str, Any]:
    """
    Run exact-reference matching followed by fallback matching.
    """

    try:
        invoices, invoices_validation = await _read_validated_csv(
            file=invoices_file,
            dataset_type="invoices",
        )

        payments, payments_validation = await _read_validated_csv(
            file=payments_file,
            dataset_type="payments",
        )

        bank_transactions, bank_validation = await _read_validated_csv(
            file=bank_transactions_file,
            dataset_type="bank_transactions",
        )

        matching_result = match_with_fallbacks(
            invoices=invoices,
            payments=payments,
            bank_transactions=bank_transactions,
        )

        return {
            "reconciliation_type": (
                "deterministic_exact_reference_with_fallbacks"
            ),
            "source_validation": {
                "invoices": invoices_validation,
                "payments": payments_validation,
                "bank_transactions": bank_validation,
            },
            **matching_result,
        }
    finally:
        await invoices_file.close()
        await payments_file.close()
        await bank_transactions_file.close()


@app.post("/evaluate/fallback", tags=["Evaluation"])
async def evaluate_fallback_reconciliation(
    invoices_file: UploadFile = File(
        ...,
        description="Invoice CSV dataset.",
    ),
    payments_file: UploadFile = File(
        ...,
        description="Payment CSV dataset.",
    ),
    bank_transactions_file: UploadFile = File(
        ...,
        description="Bank transaction CSV dataset.",
    ),
    expected_matches_file: UploadFile = File(
        ...,
        description="Labelled expected reconciliation results.",
    ),
) -> dict[str, Any]:
    """
    Run fallback reconciliation and compare it with labelled ground truth.

    The evaluation calculates:

    - Status accuracy
    - Complete-case accuracy
    - Link precision
    - Link recall
    - Link F1 score
    - Confirmed-match precision
    - Manual-review rate
    - Automatic-confirmation rate
    """

    try:
        invoices, invoices_validation = await _read_validated_csv(
            file=invoices_file,
            dataset_type="invoices",
        )

        payments, payments_validation = await _read_validated_csv(
            file=payments_file,
            dataset_type="payments",
        )

        bank_transactions, bank_validation = await _read_validated_csv(
            file=bank_transactions_file,
            dataset_type="bank_transactions",
        )

        expected_matches = await _read_expected_matches_csv(
            expected_matches_file
        )

        matching_result = match_with_fallbacks(
            invoices=invoices,
            payments=payments,
            bank_transactions=bank_transactions,
        )

        try:
            evaluation_result = evaluate_reconciliation(
                matching_result=matching_result,
                expected_matches=expected_matches,
            )
        except ReconciliationEvaluationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error

        return {
            "evaluation_type": (
                "deterministic_fallback_reconciliation_evaluation"
            ),
            "source_validation": {
                "invoices": invoices_validation,
                "payments": payments_validation,
                "bank_transactions": bank_validation,
                "expected_matches": {
                    "filename": expected_matches_file.filename,
                    "row_count": int(len(expected_matches)),
                    "columns": list(expected_matches.columns),
                },
            },
            "reconciliation": matching_result,
            "evaluation": evaluation_result,
        }
    finally:
        await invoices_file.close()
        await payments_file.close()
        await bank_transactions_file.close()
        await expected_matches_file.close()
@app.post("/analyze/mock", tags=["AI Review"])
@app.post("/analyze/mock", tags=["AI Review"])
async def analyze_with_mock_ai(
    invoices_file: UploadFile = File(
        ...,
        description="Invoice CSV dataset.",
    ),
    payments_file: UploadFile = File(
        ...,
        description="Payment CSV dataset.",
    ),
    bank_transactions_file: UploadFile = File(
        ...,
        description="Bank transaction CSV dataset.",
    ),
) -> dict[str, Any]:
    """
    Run deterministic reconciliation followed by mock AI analysis.

    Only uncertain cases are sent for AI analysis:

    - review
    - duplicate_review
    - unmatched

    Deterministically confirmed records are excluded.

    The mock analyser:

    - Makes no external API request
    - Requires no API key
    - Produces predictable recommendations
    - Never makes a final financial decision
    - Always requires human review
    """

    try:
        invoices, invoices_validation = await _read_validated_csv(
            file=invoices_file,
            dataset_type="invoices",
        )

        payments, payments_validation = await _read_validated_csv(
            file=payments_file,
            dataset_type="payments",
        )

        bank_transactions, bank_validation = await _read_validated_csv(
            file=bank_transactions_file,
            dataset_type="bank_transactions",
        )

        matching_result = match_with_fallbacks(
            invoices=invoices,
            payments=payments,
            bank_transactions=bank_transactions,
        )

        ai_analysis = analyze_reconciliation_candidates(
            matching_result=matching_result,
            analyzer=MockAIAnalyzer(),
        )

        return {
            "analysis_type": (
                "mock_ai_assisted_reconciliation_review"
            ),
            "source_validation": {
                "invoices": invoices_validation,
                "payments": payments_validation,
                "bank_transactions": bank_validation,
            },
            "reconciliation": matching_result,
            "ai_analysis": ai_analysis,
            "safety_policy": {
                "confirmed_records_sent_to_ai": False,
                "ai_can_confirm_financial_matches": False,
                "human_review_required": True,
                "maximum_ai_confidence_score": 95,
            },
        }
    finally:
        await invoices_file.close()
        await payments_file.close()
        await bank_transactions_file.close()


@app.post("/analyze/groq", tags=["AI Review"])
async def analyze_with_groq(
    invoices_file: UploadFile = File(
        ...,
        description="Invoice CSV dataset.",
    ),
    payments_file: UploadFile = File(
        ...,
        description="Payment CSV dataset.",
    ),
    bank_transactions_file: UploadFile = File(
        ...,
        description="Bank transaction CSV dataset.",
    ),
) -> dict[str, Any]:
    """
    Run deterministic reconciliation followed by live Groq analysis.

    Only uncertain records are sent to Groq:

    - review
    - duplicate_review
    - unmatched

    Deterministically confirmed records are excluded.
    Every Groq recommendation requires human review.
    """

    try:
        invoices, invoices_validation = await _read_validated_csv(
            file=invoices_file,
            dataset_type="invoices",
        )

        payments, payments_validation = await _read_validated_csv(
            file=payments_file,
            dataset_type="payments",
        )

        bank_transactions, bank_validation = await _read_validated_csv(
            file=bank_transactions_file,
            dataset_type="bank_transactions",
        )

        matching_result = match_with_fallbacks(
            invoices=invoices,
            payments=payments,
            bank_transactions=bank_transactions,
        )

        try:
            analyzer = GroqAnalyzer()
        except ValueError as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "error_code": "groq_not_configured",
                    "message": str(error),
                },
            ) from error

        try:
            ai_analysis = await run_in_threadpool(
                analyze_reconciliation_candidates,
                matching_result,
                analyzer,
            )
        except GroqAnalysisError as error:
            raise HTTPException(
                status_code=502,
                detail={
                    "error_code": "groq_analysis_failed",
                    "message": str(error),
                },
            ) from error

        return {
            "analysis_type": (
                "live_groq_assisted_reconciliation_review"
            ),
            "source_validation": {
                "invoices": invoices_validation,
                "payments": payments_validation,
                "bank_transactions": bank_validation,
            },
            "reconciliation": matching_result,
            "ai_analysis": ai_analysis,
            "safety_policy": {
                "confirmed_records_sent_to_ai": False,
                "ai_can_confirm_financial_matches": False,
                "human_review_required": True,
                "maximum_ai_confidence_score": 95,
            },
        }
    finally:
        await invoices_file.close()
        await payments_file.close()
        await bank_transactions_file.close()