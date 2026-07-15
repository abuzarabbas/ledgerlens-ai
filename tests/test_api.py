from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data" / "synthetic"


def test_root_endpoint() -> None:
    """The API root should return basic service information."""

    response = client.get("/")

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["service"] == "LedgerLens AI API"
    assert response_data["status"] == "running"
    assert response_data["documentation"] == "/docs"


def test_health_endpoint() -> None:
    """The health endpoint should confirm service availability."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "ledgerlens-ai-backend",
    }


def test_validate_invoices_dataset() -> None:
    """The invoice dataset should pass schema and data validation."""

    invoice_path = DATA_DIRECTORY / "invoices.csv"

    with invoice_path.open("rb") as invoice_file:
        response = client.post(
            "/validate/invoices",
            files={
                "file": (
                    "invoices.csv",
                    invoice_file,
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["valid"] is True
    assert response_data["dataset_type"] == "invoices"
    assert response_data["row_count"] == 10
    assert response_data["column_count"] == 9
    assert response_data["duplicate_rows"] == 0
    assert response_data["quality_warnings"] == []


def test_validate_payments_dataset_with_warnings() -> None:
    """
    The payment dataset should pass validation while reporting
    intentionally missing optional information.
    """

    payments_path = DATA_DIRECTORY / "payments.csv"

    with payments_path.open("rb") as payments_file:
        response = client.post(
            "/validate/payments",
            files={
                "file": (
                    "payments.csv",
                    payments_file,
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["valid"] is True
    assert response_data["row_count"] == 11
    assert response_data["missing_value_counts"] == {
        "customer_id": 1,
        "payment_reference": 3,
    }


def test_invalid_dataset_type_is_rejected() -> None:
    """Unsupported dataset types should return a validation error."""

    invoice_path = DATA_DIRECTORY / "invoices.csv"

    with invoice_path.open("rb") as invoice_file:
        response = client.post(
            "/validate/unsupported",
            files={
                "file": (
                    "invoices.csv",
                    invoice_file,
                    "text/csv",
                )
            },
        )

    assert response.status_code == 422
    assert "Unsupported dataset type" in response.json()["detail"]


def test_fallback_reconciliation_results() -> None:
    """
    Fallback reconciliation should produce the expected workflow
    classifications and calibrated confidence scores.
    """

    invoice_path = DATA_DIRECTORY / "invoices.csv"
    payments_path = DATA_DIRECTORY / "payments.csv"
    bank_path = DATA_DIRECTORY / "bank-transactions.csv"

    with (
        invoice_path.open("rb") as invoice_file,
        payments_path.open("rb") as payments_file,
        bank_path.open("rb") as bank_file,
    ):
        response = client.post(
            "/reconcile/fallback",
            files={
                "invoices_file": (
                    "invoices.csv",
                    invoice_file,
                    "text/csv",
                ),
                "payments_file": (
                    "payments.csv",
                    payments_file,
                    "text/csv",
                ),
                "bank_transactions_file": (
                    "bank-transactions.csv",
                    bank_file,
                    "text/csv",
                ),
            },
        )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["status_counts"] == {
        "confirmed": 4,
        "review": 5,
        "duplicate_review": 1,
        "unmatched": 0,
    }

    results_by_invoice = {
        result["invoice_id"]: result
        for result in response_data["results"]
    }

    assert results_by_invoice["INV-1001"]["status"] == "confirmed"
    assert results_by_invoice["INV-1001"]["confidence_score"] == 100

    assert results_by_invoice["INV-1003"]["status"] == "review"
    assert (
        results_by_invoice["INV-1003"]["matching_method"]
        == "amount_currency_customer_date"
    )
    assert results_by_invoice["INV-1003"]["confidence_score"] == 90

    assert results_by_invoice["INV-1004"]["confidence_score"] == 95
    assert results_by_invoice["INV-1008"]["confidence_score"] == 95

    assert (
        results_by_invoice["INV-1006"]["status"]
        == "duplicate_review"
    )

    assert "currency_mismatch" in (
        results_by_invoice["INV-1009"]["conflicts"]
    )


def test_evaluation_metrics() -> None:
    """
    The evaluation endpoint should compare predictions with the
    labelled ground-truth dataset.
    """

    invoice_path = DATA_DIRECTORY / "invoices.csv"
    payments_path = DATA_DIRECTORY / "payments.csv"
    bank_path = DATA_DIRECTORY / "bank-transactions.csv"
    expected_path = DATA_DIRECTORY / "expected-matches.csv"

    with (
        invoice_path.open("rb") as invoice_file,
        payments_path.open("rb") as payments_file,
        bank_path.open("rb") as bank_file,
        expected_path.open("rb") as expected_file,
    ):
        response = client.post(
            "/evaluate/fallback",
            files={
                "invoices_file": (
                    "invoices.csv",
                    invoice_file,
                    "text/csv",
                ),
                "payments_file": (
                    "payments.csv",
                    payments_file,
                    "text/csv",
                ),
                "bank_transactions_file": (
                    "bank-transactions.csv",
                    bank_file,
                    "text/csv",
                ),
                "expected_matches_file": (
                    "expected-matches.csv",
                    expected_file,
                    "text/csv",
                ),
            },
        )

    assert response.status_code == 200

    response_data = response.json()
    evaluation = response_data["evaluation"]
    scope = evaluation["evaluation_scope"]
    metrics = evaluation["metrics"]

    assert scope["expected_rows"] == 12
    assert scope["evaluated_invoices"] == 10
    assert scope["unsupported_rows_without_invoice_id"] == 1
    assert scope["extra_prediction_invoice_ids"] == []

    assert metrics["status_accuracy"] == 1.0
    assert metrics["complete_case_accuracy"] == 1.0
    assert metrics["link_precision"] == 1.0
    assert metrics["link_recall"] == 1.0
    assert metrics["link_f1_score"] == 1.0
    assert metrics["confirmed_match_precision"] == 1.0
    assert metrics["manual_review_rate"] == 0.6
    assert metrics["automatic_confirmation_rate"] == 0.4
    assert metrics["unmatched_prediction_rate"] == 0.0


def test_non_csv_file_is_rejected() -> None:
    """The validation endpoint should reject unsupported file types."""

    response = client.post(
        "/validate/invoices",
        files={
            "file": (
                "invoices.txt",
                b"not,a,csv",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "The invoices file must be a CSV file."