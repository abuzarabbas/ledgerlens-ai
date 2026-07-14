from fastapi import FastAPI, HTTPException, UploadFile, status

from backend.validators import CSVValidationError, validate_csv


app = FastAPI(
    title="LedgerLens AI API",
    description=(
        "Backend API for validating financial data, matching invoices, "
        "payments and bank transactions, and supporting human review."
    ),
    version="0.2.0",
)


@app.get("/", tags=["System"])
async def root() -> dict[str, str]:
    """Return basic information about the LedgerLens AI API."""
    return {
        "service": "LedgerLens AI API",
        "version": "0.2.0",
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
    file: UploadFile,
) -> dict[str, object]:
    """
    Validate an uploaded LedgerLens CSV dataset.

    Supported dataset types:

    - invoices
    - payments
    - bank_transactions
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file must have a filename.",
        )

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported.",
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
            detail=str(error),
        ) from error
    finally:
        await file.close()

    return {
        "filename": file.filename,
        **validation_result,
    }