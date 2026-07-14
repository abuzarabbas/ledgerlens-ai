from fastapi import FastAPI

app = FastAPI(
    title="LedgerLens AI API",
    description=(
        "Backend API for validating financial data, matching invoices, "
        "payments and bank transactions, and supporting human review."
    ),
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    """Return basic information about the LedgerLens AI API."""
    return {
        "service": "LedgerLens AI API",
        "version": "0.1.0",
        "status": "running",
        "documentation": "/docs",
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Confirm that the backend service is available."""
    return {
        "status": "healthy",
        "service": "ledgerlens-ai-backend",
    }
