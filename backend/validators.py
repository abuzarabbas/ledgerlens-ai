from io import BytesIO
from typing import Final

import pandas as pd


REQUIRED_COLUMNS: Final[dict[str, set[str]]] = {
    "invoices": {
        "invoice_id",
        "customer_id",
        "customer_name",
        "invoice_date",
        "due_date",
        "currency",
        "invoice_amount",
        "invoice_reference",
        "status",
    },
    "payments": {
        "payment_id",
        "customer_id",
        "payment_date",
        "currency",
        "payment_amount",
        "payment_reference",
        "payment_description",
    },
    "bank_transactions": {
        "transaction_id",
        "booking_date",
        "value_date",
        "currency",
        "transaction_amount",
        "sender_name",
        "bank_reference",
        "description",
    },
}


class CSVValidationError(ValueError):
    """Raised when an uploaded CSV file fails validation."""


def validate_csv(content: bytes, dataset_type: str) -> dict[str, object]:
    """
    Validate a CSV file against the expected LedgerLens schema.

    Args:
        content: Raw CSV file content.
        dataset_type: One of invoices, payments or bank_transactions.

    Returns:
        A validation summary containing row and duplicate counts.

    Raises:
        CSVValidationError: If the file is empty, malformed or missing columns.
    """

    if dataset_type not in REQUIRED_COLUMNS:
        supported_types = ", ".join(sorted(REQUIRED_COLUMNS))
        raise CSVValidationError(
            f"Unsupported dataset type '{dataset_type}'. "
            f"Supported types: {supported_types}."
        )

    if not content or not content.strip():
        raise CSVValidationError("The uploaded CSV file is empty.")

    try:
        dataframe = pd.read_csv(BytesIO(content))
    except UnicodeDecodeError as exc:
        raise CSVValidationError(
            "The file could not be decoded. Please upload a UTF-8 CSV file."
        ) from exc
    except pd.errors.EmptyDataError as exc:
        raise CSVValidationError(
            "The uploaded CSV file contains no readable data."
        ) from exc
    except pd.errors.ParserError as exc:
        raise CSVValidationError(
            "The CSV structure is invalid or inconsistent."
        ) from exc

    dataframe.columns = [
        str(column).strip() for column in dataframe.columns
    ]

    required_columns = REQUIRED_COLUMNS[dataset_type]
    uploaded_columns = set(dataframe.columns)

    missing_columns = sorted(required_columns - uploaded_columns)

    if missing_columns:
        raise CSVValidationError(
            "Missing required columns: " + ", ".join(missing_columns)
        )

    if dataframe.empty:
        raise CSVValidationError(
            "The CSV contains column headers but no data records."
        )

    duplicate_rows = int(dataframe.duplicated().sum())

    return {
        "valid": True,
        "dataset_type": dataset_type,
        "row_count": int(len(dataframe)),
        "column_count": int(len(dataframe.columns)),
        "duplicate_rows": duplicate_rows,
        "columns": list(dataframe.columns),
    }