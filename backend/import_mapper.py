import re
from typing import Any

import pandas as pd


class ImportMappingError(ValueError):
    """
    Raised when an uploaded dataset cannot be mapped safely.
    """


DATASET_FIELDS: dict[str, list[str]] = {
    "invoices": [
        "invoice_id",
        "customer_id",
        "customer_name",
        "invoice_date",
        "due_date",
        "currency",
        "invoice_amount",
        "invoice_reference",
        "status",
    ],
    "payments": [
        "payment_id",
        "customer_id",
        "payment_date",
        "currency",
        "payment_amount",
        "payment_reference",
        "payment_description",
    ],
    "bank_transactions": [
        "transaction_id",
        "booking_date",
        "value_date",
        "currency",
        "transaction_amount",
        "sender_name",
        "bank_reference",
        "description",
    ],
}


REQUIRED_FIELDS: dict[str, set[str]] = {
    "invoices": {
        "invoice_id",
        "invoice_date",
        "currency",
        "invoice_amount",
    },
    "payments": {
        "payment_id",
        "payment_date",
        "currency",
        "payment_amount",
    },
    "bank_transactions": {
        "transaction_id",
        "booking_date",
        "currency",
        "transaction_amount",
    },
}


FIELD_ALIASES: dict[str, dict[str, list[str]]] = {
    "invoices": {
        "invoice_id": [
            "invoice number",
            "invoice no",
            "invoice num",
            "invoice identifier",
            "document number",
            "document id",
            "bill number",
        ],
        "customer_id": [
            "client id",
            "account id",
            "customer number",
            "customer no",
            "debtor id",
            "debtor number",
        ],
        "customer_name": [
            "customer",
            "client",
            "client name",
            "account name",
            "debtor",
            "debtor name",
            "company name",
        ],
 "invoice_date": [
    "date",
    "document date",
    "billing date",
    "issue date",
    "issued date",
    "posting date",
    "posted date",
],
        "due_date": [
            "payment due date",
            "due",
            "maturity date",
        ],
        "currency": [
            "currency code",
            "curr",
            "iso currency",
        ],
        "invoice_amount": [
            "amount",
            "invoice total",
            "total",
            "gross amount",
            "gross total",
            "total amount",
            "invoice value",
        ],
        "invoice_reference": [
            "reference",
            "invoice ref",
            "payment reference",
            "remittance reference",
            "document reference",
        ],
        "status": [
            "invoice status",
            "payment status",
            "document status",
            "state",
        ],
    },
    "payments": {
        "payment_id": [
            "payment number",
            "payment no",
            "payment identifier",
            "receipt id",
            "receipt number",
        ],
        "customer_id": [
            "client id",
            "account id",
            "customer number",
            "customer no",
            "debtor id",
        ],
        "payment_date": [
            "date",
            "received date",
            "receipt date",
            "transaction date",
            "posted date",
        ],
        "currency": [
            "currency code",
            "curr",
            "iso currency",
        ],
        "payment_amount": [
            "amount",
            "paid amount",
            "received amount",
            "receipt amount",
            "payment total",
        ],
        "payment_reference": [
            "reference",
            "payment ref",
            "invoice reference",
            "remittance reference",
        ],
        "payment_description": [
            "description",
            "memo",
            "payment memo",
            "notes",
            "details",
            "narrative",
        ],
    },
    "bank_transactions": {
        "transaction_id": [
            "transaction number",
            "transaction no",
            "bank transaction id",
            "entry id",
            "booking id",
        ],
        "booking_date": [
            "date",
            "transaction date",
            "posted date",
            "posting date",
            "booking day",
        ],
        "value_date": [
            "settlement date",
            "effective date",
            "value day",
        ],
        "currency": [
            "currency code",
            "curr",
            "iso currency",
        ],
        "transaction_amount": [
            "amount",
            "bank amount",
            "transaction value",
            "credit amount",
            "net amount",
        ],
        "sender_name": [
            "sender",
            "counterparty",
            "counterparty name",
            "payer",
            "payer name",
            "originator",
            "account holder",
        ],
        "bank_reference": [
            "reference",
            "bank ref",
            "transaction reference",
            "payment reference",
            "remittance reference",
        ],
        "description": [
            "memo",
            "transaction description",
            "narrative",
            "details",
            "purpose",
            "payment details",
        ],
    },
}


def _normalise_column_name(value: Any) -> str:
    """
    Convert a source column name into a comparable identifier.
    """

    text = str(value).strip().lower()

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    )

    return text.strip("_")


def _validate_dataset_type(dataset_type: str) -> None:
    """
    Ensure the requested dataset type is supported.
    """

    if dataset_type not in DATASET_FIELDS:
        supported = ", ".join(
            sorted(DATASET_FIELDS)
        )

        raise ImportMappingError(
            f"Unsupported dataset type '{dataset_type}'. "
            f"Supported types: {supported}."
        )


def _build_alias_lookup(
    dataset_type: str,
) -> dict[str, str]:
    """
    Build a normalised alias-to-canonical-field lookup.
    """

    lookup: dict[str, str] = {}

    for canonical_field in DATASET_FIELDS[dataset_type]:
        lookup[
            _normalise_column_name(canonical_field)
        ] = canonical_field

        aliases = FIELD_ALIASES[
            dataset_type
        ].get(
            canonical_field,
            [],
        )

        for alias in aliases:
            lookup[
                _normalise_column_name(alias)
            ] = canonical_field

    return lookup


def suggest_column_mapping(
    source_columns: list[Any],
    dataset_type: str,
) -> dict[str, Any]:
    """
    Suggest canonical LedgerLens fields for uploaded columns.

    Suggestions use conservative exact alias matching. Unrecognised
    columns remain unmapped so users can map them manually.
    """

    _validate_dataset_type(dataset_type)

    clean_source_columns = [
        str(column).strip()
        for column in source_columns
    ]

    alias_lookup = _build_alias_lookup(
        dataset_type
    )

    suggested_mapping: dict[str, str | None] = {
        field: None
        for field in DATASET_FIELDS[dataset_type]
    }

    mapping_confidence: dict[str, float] = {
        field: 0.0
        for field in DATASET_FIELDS[dataset_type]
    }

    used_source_columns: set[str] = set()

    for source_column in clean_source_columns:
        normalised_source = _normalise_column_name(
            source_column
        )

        canonical_field = alias_lookup.get(
            normalised_source
        )

        if canonical_field is None:
            continue

        if suggested_mapping[canonical_field] is not None:
            continue

        if source_column in used_source_columns:
            continue

        suggested_mapping[canonical_field] = (
            source_column
        )

        used_source_columns.add(
            source_column
        )

        canonical_normalised = (
            _normalise_column_name(
                canonical_field
            )
        )

        mapping_confidence[canonical_field] = (
            1.0
            if normalised_source
            == canonical_normalised
            else 0.95
        )

    missing_required_fields = sorted(
        field
        for field in REQUIRED_FIELDS[dataset_type]
        if suggested_mapping[field] is None
    )

    unmapped_source_columns = [
        column
        for column in clean_source_columns
        if column not in used_source_columns
    ]

    return {
        "dataset_type": dataset_type,
        "source_columns": clean_source_columns,
        "canonical_fields": DATASET_FIELDS[
            dataset_type
        ],
        "required_fields": sorted(
            REQUIRED_FIELDS[dataset_type]
        ),
        "suggested_mapping": suggested_mapping,
        "mapping_confidence": mapping_confidence,
        "missing_required_fields": (
            missing_required_fields
        ),
        "unmapped_source_columns": (
            unmapped_source_columns
        ),
        "ready_to_normalize": (
            len(missing_required_fields) == 0
        ),
    }


def apply_column_mapping(
    dataframe: pd.DataFrame,
    dataset_type: str,
    mapping: dict[str, str | None],
) -> pd.DataFrame:
    """
    Convert a source dataframe into the canonical LedgerLens schema.

    Required fields must be mapped. Optional fields that are not
    available are created as empty columns.
    """

    _validate_dataset_type(dataset_type)

    if dataframe.empty:
        raise ImportMappingError(
            "The uploaded dataset contains no rows."
        )

    canonical_fields = DATASET_FIELDS[
        dataset_type
    ]

    unknown_target_fields = sorted(
        set(mapping) - set(canonical_fields)
    )

    if unknown_target_fields:
        raise ImportMappingError(
            "The mapping contains unsupported canonical "
            f"field(s): {', '.join(unknown_target_fields)}."
        )

    resolved_mapping: dict[str, str | None] = {
        field: mapping.get(field)
        for field in canonical_fields
    }

    missing_required_fields = sorted(
        field
        for field in REQUIRED_FIELDS[dataset_type]
        if not resolved_mapping.get(field)
    )

    if missing_required_fields:
        raise ImportMappingError(
            "Required canonical field(s) are not mapped: "
            f"{', '.join(missing_required_fields)}."
        )

    selected_sources = [
        source
        for source in resolved_mapping.values()
        if source
    ]

    duplicate_sources = sorted(
        {
            source
            for source in selected_sources
            if selected_sources.count(source) > 1
        }
    )

    if duplicate_sources:
        raise ImportMappingError(
            "A source column cannot be mapped to multiple "
            "canonical fields. Duplicate source column(s): "
            f"{', '.join(duplicate_sources)}."
        )

    missing_source_columns = sorted(
        source
        for source in selected_sources
        if source not in dataframe.columns
    )

    if missing_source_columns:
        raise ImportMappingError(
            "Mapped source column(s) were not found in the "
            f"uploaded dataset: {', '.join(missing_source_columns)}."
        )

    normalized_dataframe = pd.DataFrame(
        index=dataframe.index
    )

    for canonical_field in canonical_fields:
        source_column = resolved_mapping.get(
            canonical_field
        )

        if source_column:
            normalized_dataframe[
                canonical_field
            ] = dataframe[source_column]
        else:
            normalized_dataframe[
                canonical_field
            ] = pd.NA

    return normalized_dataframe.reset_index(
        drop=True
    )