from io import BytesIO
from typing import Final

import pandas as pd


DATASET_RULES: Final[dict[str, dict[str, object]]] = {
    "invoices": {
        "required_columns": {
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
        "id_column": "invoice_id",
        "date_columns": ["invoice_date", "due_date"],
        "amount_column": "invoice_amount",
        "currency_column": "currency",
    },
    "payments": {
        "required_columns": {
            "payment_id",
            "customer_id",
            "payment_date",
            "currency",
            "payment_amount",
            "payment_reference",
            "payment_description",
        },
        "id_column": "payment_id",
        "date_columns": ["payment_date"],
        "amount_column": "payment_amount",
        "currency_column": "currency",
    },
    "bank_transactions": {
        "required_columns": {
            "transaction_id",
            "booking_date",
            "value_date",
            "currency",
            "transaction_amount",
            "sender_name",
            "bank_reference",
            "description",
        },
        "id_column": "transaction_id",
        "date_columns": ["booking_date", "value_date"],
        "amount_column": "transaction_amount",
        "currency_column": "currency",
    },
}


class CSVValidationError(ValueError):
    """Raised when an uploaded CSV file fails validation."""


def _row_numbers(mask: pd.Series) -> list[int]:
    """
    Convert DataFrame indexes to human-readable CSV row numbers.

    Two is added because CSV row 1 contains the column headers.
    """
    return [int(index) + 2 for index in mask[mask].index]


def validate_csv(content: bytes, dataset_type: str) -> dict[str, object]:
    """
    Validate a LedgerLens CSV file.

    Validation includes:

    - Required columns
    - Empty files
    - Missing record identifiers
    - Duplicate identifiers
    - Invalid dates
    - Invalid or non-positive amounts
    - Invalid currency codes
    - Exact duplicate rows
    - Missing optional values
    """

    if dataset_type not in DATASET_RULES:
        supported_types = ", ".join(sorted(DATASET_RULES))

        raise CSVValidationError(
            f"Unsupported dataset type '{dataset_type}'. "
            f"Supported types: {supported_types}."
        )

    if not content or not content.strip():
        raise CSVValidationError("The uploaded CSV file is empty.")

    try:
        dataframe = pd.read_csv(BytesIO(content), dtype=str)
    except UnicodeDecodeError as error:
        raise CSVValidationError(
            "The file could not be decoded. Upload a UTF-8 CSV file."
        ) from error
    except pd.errors.EmptyDataError as error:
        raise CSVValidationError(
            "The uploaded CSV file contains no readable data."
        ) from error
    except pd.errors.ParserError as error:
        raise CSVValidationError(
            "The CSV structure is invalid or inconsistent."
        ) from error

    dataframe.columns = [
        str(column).strip() for column in dataframe.columns
    ]

    dataframe = dataframe.map(
        lambda value: value.strip() if isinstance(value, str) else value
    )

    dataframe = dataframe.replace(r"^\s*$", pd.NA, regex=True)

    rules = DATASET_RULES[dataset_type]

    required_columns = set(rules["required_columns"])
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

    errors: list[str] = []
    warnings: list[str] = []

    id_column = str(rules["id_column"])
    date_columns = list(rules["date_columns"])
    amount_column = str(rules["amount_column"])
    currency_column = str(rules["currency_column"])

    critical_columns = {
        id_column,
        amount_column,
        currency_column,
        *date_columns,
    }

    # Validate record identifiers.
    missing_id_mask = dataframe[id_column].isna()

    if missing_id_mask.any():
        errors.append(
            f"Missing {id_column} values in CSV rows "
            f"{_row_numbers(missing_id_mask)}."
        )

    duplicate_id_mask = (
        dataframe[id_column].notna()
        & dataframe[id_column].duplicated(keep=False)
    )

    if duplicate_id_mask.any():
        duplicate_ids = sorted(
            dataframe.loc[duplicate_id_mask, id_column]
            .dropna()
            .unique()
            .tolist()
        )

        errors.append(
            f"Duplicate {id_column} values found: {duplicate_ids}."
        )

    # Validate date columns.
    parsed_dates: dict[str, pd.Series] = {}

    for date_column in date_columns:
        missing_date_mask = dataframe[date_column].isna()

        if missing_date_mask.any():
            errors.append(
                f"Missing {date_column} values in CSV rows "
                f"{_row_numbers(missing_date_mask)}."
            )

        parsed_date = pd.to_datetime(
            dataframe[date_column],
            errors="coerce",
        )

        parsed_dates[date_column] = parsed_date

        invalid_date_mask = (
            dataframe[date_column].notna()
            & parsed_date.isna()
        )

        if invalid_date_mask.any():
            errors.append(
                f"Invalid {date_column} values in CSV rows "
                f"{_row_numbers(invalid_date_mask)}."
            )

    # Validate invoice date relationships.
    if dataset_type == "invoices":
        invoice_dates = parsed_dates["invoice_date"]
        due_dates = parsed_dates["due_date"]

        due_before_invoice_mask = (
            invoice_dates.notna()
            & due_dates.notna()
            & (due_dates < invoice_dates)
        )

        if due_before_invoice_mask.any():
            warnings.append(
                "Due date occurs before invoice date in CSV rows "
                f"{_row_numbers(due_before_invoice_mask)}."
            )

    # Validate amounts.
    numeric_amounts = pd.to_numeric(
        dataframe[amount_column],
        errors="coerce",
    )

    invalid_amount_mask = (
        dataframe[amount_column].isna()
        | numeric_amounts.isna()
        | (numeric_amounts <= 0)
    )

    if invalid_amount_mask.any():
        errors.append(
            f"Missing, invalid or non-positive {amount_column} values "
            f"in CSV rows {_row_numbers(invalid_amount_mask)}."
        )

    # Validate three-letter currency codes.
    normalised_currency = (
        dataframe[currency_column]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    invalid_currency_mask = (
        dataframe[currency_column].isna()
        | ~normalised_currency.str.match(
            r"^[A-Z]{3}$",
            na=False,
        )
    )

    if invalid_currency_mask.any():
        errors.append(
            f"Invalid {currency_column} values in CSV rows "
            f"{_row_numbers(invalid_currency_mask)}. "
            "Use three-letter currency codes such as EUR or USD."
        )

    # Detect completely duplicated rows.
    exact_duplicate_mask = dataframe.duplicated(keep=False)
    duplicate_rows = int(dataframe.duplicated().sum())

    if exact_duplicate_mask.any():
        warnings.append(
            "Exact duplicate records found in CSV rows "
            f"{_row_numbers(exact_duplicate_mask)}."
        )

    # Report missing values in non-critical fields as warnings.
    missing_value_counts: dict[str, int] = {}

    for column in dataframe.columns:
        missing_count = int(dataframe[column].isna().sum())

        if missing_count > 0:
            missing_value_counts[column] = missing_count

            if column not in critical_columns:
                warnings.append(
                    f"Column '{column}' contains "
                    f"{missing_count} missing value(s)."
                )

    if errors:
        raise CSVValidationError(" | ".join(errors))

    return {
        "valid": True,
        "dataset_type": dataset_type,
        "row_count": int(len(dataframe)),
        "column_count": int(len(dataframe.columns)),
        "duplicate_rows": duplicate_rows,
        "columns": list(dataframe.columns),
        "missing_value_counts": missing_value_counts,
        "quality_warnings": warnings,
    }