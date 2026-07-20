import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from backend.import_normalize import (
    CSVNormalizationError,
    normalize_csv_import,
)
from backend.main import app


client = TestClient(app)


def _read_normalized_csv(
    csv_content: str,
) -> list[dict[str, str]]:
    return list(
        csv.DictReader(
            io.StringIO(csv_content)
        )
    )


def test_normalizes_real_invoice_column_names() -> None:
    csv_content = (
        "Document Number,Client,Posting Date,"
        "Currency Code,Gross Value,Reference\n"
        "INV-REAL-1,Example GmbH,2026-07-20,"
        "EUR,1250.50,REF-100\n"
    )

    result = normalize_csv_import(
        file_bytes=csv_content.encode("utf-8"),
        filename="real-invoices.csv",
        dataset_type="invoices",
        mapping={
            "invoice_id": "Document Number",
            "customer_name": "Client",
            "invoice_date": "Posting Date",
            "currency": "Currency Code",
            "invoice_amount": "Gross Value",
            "invoice_reference": "Reference",
        },
    )

    assert result["row_count"] == 1

    assert result["canonical_columns"] == [
        "invoice_id",
        "customer_id",
        "customer_name",
        "invoice_date",
        "due_date",
        "currency",
        "invoice_amount",
        "invoice_reference",
        "status",
    ]

    rows = _read_normalized_csv(
        result["normalized_csv"]
    )

    assert rows[0]["invoice_id"] == "INV-REAL-1"
    assert rows[0]["customer_name"] == "Example GmbH"
    assert rows[0]["invoice_date"] == "2026-07-20"
    assert rows[0]["invoice_amount"] == "1250.50"
    assert rows[0]["customer_id"] == ""


def test_normalizes_semicolon_payment_csv() -> None:
    csv_content = (
        "Payment Number;Received Date;"
        "Currency Code;Paid Amount\n"
        "PAY-1;2026-07-20;EUR;500.00\n"
    )

    result = normalize_csv_import(
        file_bytes=csv_content.encode("utf-8"),
        filename="payments.csv",
        dataset_type="payments",
        mapping={
            "payment_id": "Payment Number",
            "payment_date": "Received Date",
            "currency": "Currency Code",
            "payment_amount": "Paid Amount",
        },
    )

    rows = _read_normalized_csv(
        result["normalized_csv"]
    )

    assert rows[0]["payment_id"] == "PAY-1"
    assert rows[0]["payment_amount"] == "500.00"


def test_normalization_rejects_missing_required_mapping() -> None:
    csv_content = (
        "Document Number,Posting Date\n"
        "INV-1,2026-07-20\n"
    )

    with pytest.raises(
        ValueError,
        match="Required canonical field",
    ):
        normalize_csv_import(
            file_bytes=csv_content.encode("utf-8"),
            filename="invoices.csv",
            dataset_type="invoices",
            mapping={
                "invoice_id": "Document Number",
                "invoice_date": "Posting Date",
            },
        )


def test_normalization_rejects_duplicate_mapping() -> None:
    csv_content = (
        "Identifier,Date,Currency,Amount\n"
        "INV-1,2026-07-20,EUR,100.00\n"
    )

    with pytest.raises(
        ValueError,
        match="cannot be mapped to multiple",
    ):
        normalize_csv_import(
            file_bytes=csv_content.encode("utf-8"),
            filename="invoices.csv",
            dataset_type="invoices",
            mapping={
                "invoice_id": "Identifier",
                "invoice_date": "Identifier",
                "currency": "Currency",
                "invoice_amount": "Amount",
            },
        )


def test_normalize_api_returns_canonical_csv() -> None:
    csv_content = (
        "Invoice Number,Invoice Date,Currency,Amount\n"
        "INV-1,2026-07-20,EUR,100.00\n"
    )

    mapping = {
        "invoice_id": "Invoice Number",
        "invoice_date": "Invoice Date",
        "currency": "Currency",
        "invoice_amount": "Amount",
    }

    response = client.post(
        "/import/normalize/invoices",
        data={
            "mapping_json": json.dumps(mapping)
        },
        files={
            "file": (
                "invoices.csv",
                csv_content,
                "text/csv",
            )
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["row_count"] == 1
    assert payload["delimiter"] == ","

    assert payload["canonical_columns"][0] == (
        "invoice_id"
    )

    assert "INV-1" in payload["normalized_csv"]


def test_normalize_api_rejects_invalid_mapping_json() -> None:
    csv_content = (
        "Invoice Number,Invoice Date,Currency,Amount\n"
        "INV-1,2026-07-20,EUR,100.00\n"
    )

    response = client.post(
        "/import/normalize/invoices",
        data={
            "mapping_json": "{invalid-json"
        },
        files={
            "file": (
                "invoices.csv",
                csv_content,
                "text/csv",
            )
        },
    )

    assert response.status_code == 400

    assert (
        "not valid JSON"
        in response.json()["detail"]
    )