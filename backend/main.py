from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, status

from backend.matcher import match_exact_references
from backend.validators import CSVValidationError, validate_csv


app = FastAPI(
    title="LedgerLens AI API",
    description=(
        "Backend API for validating financial data, matching invoices, "
        "payments and bank transactions, and supporting human review."
    ),
    version="0.3.0",
)


async def _read_validated_csv(
    file: UploadFile,
    dataset_type: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Read, validate and convert an uploaded CSV file into a DataFrame.
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


@app.get("/", tags=["System"])
async def root() -> dict[str, str]:
    """Return basic information about the LedgerLens AI API."""

    return {
        "service": "LedgerLens AI API",
        "version": "0.3.0",
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
    Reconcile invoices, payments and bank transactions using exact references.

    All three datasets are validated before matching begins.
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