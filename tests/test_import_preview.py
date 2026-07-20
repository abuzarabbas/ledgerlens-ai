import pytest
from fastapi.testclient import TestClient

import pytest
from fastapi.testclient import TestClient

from backend.import_preview import (
    CSVPreviewError,
    build_csv_preview,
)
from backend.main import app


client = TestClient(app)


def test_build_invoice_preview_and_mapping() -> None:
    csv_content = (
        "Invoice Number,Invoice Date,Currency Code,"
        "Gross Amount,Customer\n"
        "INV-1,2026-07-20,EUR,1250.50,Example GmbH\n"
        "INV-2,2026-07-21,EUR,950.00,Demo AG\n"
    )

    result = build_csv_preview(
        file_bytes=csv_content.encode("utf-8"),
        filename="invoices.csv",
        dataset_type="invoices",
    )

    assert result["filename"] == "invoices.csv"
    assert result["delimiter"] == ","
    assert result["row_count"] == 2
    assert result["column_count"] == 5

    assert result["preview_rows"][0] == {
        "Invoice Number": "INV-1",
        "Invoice Date": "2026-07-20",
        "Currency Code": "EUR",
        "Gross Amount": "1250.50",
        "Customer": "Example GmbH",
    }

    mapping = result["mapping"]

    assert mapping["ready_to_normalize"] is True

    assert mapping["suggested_mapping"][
        "invoice_id"
    ] == "Invoice Number"

    assert mapping["suggested_mapping"][
        "invoice_amount"
    ] == "Gross Amount"


def test_preview_detects_semicolon_delimiter() -> None:
    csv_content = (
        "Payment Number;Received Date;Currency;Amount\n"
        "PAY-1;2026-07-20;EUR;500.00\n"
    )

    result = build_csv_preview(
        file_bytes=csv_content.encode("utf-8"),
        filename="payments.csv",
        dataset_type="payments",
    )

    assert result["delimiter"] == ";"
    assert result["row_count"] == 1

    assert result["mapping"][
        "ready_to_normalize"
    ] is True


def test_preview_reports_missing_required_mapping() -> None:
    csv_content = (
        "Transaction ID,Booking Date,Currency,Sender\n"
        "TX-1,2026-07-20,EUR,Example GmbH\n"
    )

    result = build_csv_preview(
        file_bytes=csv_content.encode("utf-8"),
        filename="bank.csv",
        dataset_type="bank_transactions",
    )

    assert result["mapping"][
        "ready_to_normalize"
    ] is False

    assert result["mapping"][
        "missing_required_fields"
    ] == [
        "transaction_amount"
    ]


def test_preview_rejects_duplicate_headers() -> None:
    csv_content = (
        "Invoice Number,Invoice Number,"
        "Invoice Date,Currency,Amount\n"
        "INV-1,INV-1,2026-07-20,EUR,100.00\n"
    )

    with pytest.raises(
        CSVPreviewError,
        match="duplicate column",
    ):
        build_csv_preview(
            file_bytes=csv_content.encode("utf-8"),
            filename="invoices.csv",
            dataset_type="invoices",
        )


def test_preview_api_returns_mapping_suggestion() -> None:
    csv_content = (
        "Invoice Number,Invoice Date,Currency,Amount\n"
        "INV-1,2026-07-20,EUR,100.00\n"
    )

    response = client.post(
        "/import/preview/invoices",
        files={
            "file": (
                "real-invoices.csv",
                csv_content,
                "text/csv",
            )
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["filename"] == (
        "real-invoices.csv"
    )

    assert payload["row_count"] == 1

    assert payload["mapping"][
        "ready_to_normalize"
    ] is True


def test_preview_api_rejects_unknown_dataset_type() -> None:
    csv_content = (
        "ID,Date,Currency,Amount\n"
        "1,2026-07-20,EUR,100.00\n"
    )

    response = client.post(
        "/import/preview/unknown",
        files={
            "file": (
                "data.csv",
                csv_content,
                "text/csv",
            )
        },
    )

    assert response.status_code == 400

    detail = response.json()["detail"]

    assert "Unsupported dataset type" in detail