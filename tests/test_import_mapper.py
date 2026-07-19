import pandas as pd
import pytest

from backend.import_mapper import (
    DATASET_FIELDS,
    ImportMappingError,
    apply_column_mapping,
    suggest_column_mapping,
)


def test_invoice_mapping_suggests_common_aliases() -> None:
    result = suggest_column_mapping(
        source_columns=[
            "Invoice Number",
            "Client ID",
            "Customer",
            "Invoice Date",
            "Due Date",
            "Currency Code",
            "Gross Amount",
            "Reference",
            "Payment Status",
            "Internal Comment",
        ],
        dataset_type="invoices",
    )

    assert result["ready_to_normalize"] is True

    assert result["suggested_mapping"] == {
        "invoice_id": "Invoice Number",
        "customer_id": "Client ID",
        "customer_name": "Customer",
        "invoice_date": "Invoice Date",
        "due_date": "Due Date",
        "currency": "Currency Code",
        "invoice_amount": "Gross Amount",
        "invoice_reference": "Reference",
        "status": "Payment Status",
    }

    assert result["unmapped_source_columns"] == [
        "Internal Comment"
    ]


def test_bank_mapping_detects_missing_required_field() -> None:
    result = suggest_column_mapping(
        source_columns=[
            "Transaction ID",
            "Booking Date",
            "Currency",
            "Counterparty",
            "Reference",
        ],
        dataset_type="bank_transactions",
    )

    assert result["ready_to_normalize"] is False

    assert result["missing_required_fields"] == [
        "transaction_amount"
    ]


def test_apply_mapping_returns_canonical_invoice_schema() -> None:
    source_dataframe = pd.DataFrame(
        {
            "Invoice Number": ["INV-1"],
            "Invoice Date": ["2026-07-20"],
            "Currency Code": ["EUR"],
            "Gross Amount": [1250.50],
            "Customer": ["Example GmbH"],
            "Reference": ["REF-1"],
        }
    )

    normalized = apply_column_mapping(
        dataframe=source_dataframe,
        dataset_type="invoices",
        mapping={
            "invoice_id": "Invoice Number",
            "invoice_date": "Invoice Date",
            "currency": "Currency Code",
            "invoice_amount": "Gross Amount",
            "customer_name": "Customer",
            "invoice_reference": "Reference",
        },
    )

    assert list(normalized.columns) == (
        DATASET_FIELDS["invoices"]
    )

    assert normalized.loc[0, "invoice_id"] == "INV-1"
    assert normalized.loc[0, "customer_name"] == (
        "Example GmbH"
    )

    assert normalized.loc[
        0,
        "invoice_amount",
    ] == 1250.50

    assert pd.isna(
        normalized.loc[0, "customer_id"]
    )


def test_apply_mapping_rejects_missing_required_fields() -> None:
    dataframe = pd.DataFrame(
        {
            "Invoice Number": ["INV-1"],
            "Invoice Date": ["2026-07-20"],
        }
    )

    with pytest.raises(
        ImportMappingError,
        match="Required canonical field",
    ):
        apply_column_mapping(
            dataframe=dataframe,
            dataset_type="invoices",
            mapping={
                "invoice_id": "Invoice Number",
                "invoice_date": "Invoice Date",
            },
        )


def test_apply_mapping_rejects_duplicate_source_usage() -> None:
    dataframe = pd.DataFrame(
        {
            "ID": ["VALUE-1"],
            "Date": ["2026-07-20"],
            "Currency": ["EUR"],
            "Amount": [100.0],
        }
    )

    with pytest.raises(
        ImportMappingError,
        match="cannot be mapped to multiple",
    ):
        apply_column_mapping(
            dataframe=dataframe,
            dataset_type="payments",
            mapping={
                "payment_id": "ID",
                "customer_id": "ID",
                "payment_date": "Date",
                "currency": "Currency",
                "payment_amount": "Amount",
            },
        )


def test_mapping_rejects_unknown_dataset_type() -> None:
    with pytest.raises(
        ImportMappingError,
        match="Unsupported dataset type",
    ):
        suggest_column_mapping(
            source_columns=["ID", "Amount"],
            dataset_type="unknown",
        )