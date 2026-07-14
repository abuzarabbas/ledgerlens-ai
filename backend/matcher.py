from typing import Any

import pandas as pd


def _normalise_text(value: Any) -> str:
    """
    Convert a value into a clean uppercase string.

    Empty or missing values become an empty string.
    """

    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def _prepare_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy of a DataFrame with trimmed column names.
    """

    prepared = dataframe.copy()

    prepared.columns = [
        str(column).strip()
        for column in prepared.columns
    ]

    return prepared


def _records_to_list(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Convert DataFrame rows into JSON-compatible dictionaries.
    """

    clean_dataframe = dataframe.where(
        pd.notna(dataframe),
        None,
    )

    return clean_dataframe.to_dict(orient="records")


def match_exact_references(
    invoices: pd.DataFrame,
    payments: pd.DataFrame,
    bank_transactions: pd.DataFrame,
) -> dict[str, Any]:
    """
    Match invoices, payments and bank transactions using exact references.

    A match is confirmed only when:

    - Invoice reference equals payment reference
    - Invoice reference equals bank reference
    - Currency matches across all three records
    - Amount matches across all three records
    - Exactly one payment and one bank transaction are found

    Ambiguous or conflicting cases are routed to review.
    """

    invoices = _prepare_dataframe(invoices)
    payments = _prepare_dataframe(payments)
    bank_transactions = _prepare_dataframe(bank_transactions)

    invoices["_normalised_reference"] = (
        invoices["invoice_reference"].apply(_normalise_text)
    )

    payments["_normalised_reference"] = (
        payments["payment_reference"].apply(_normalise_text)
    )

    bank_transactions["_normalised_reference"] = (
        bank_transactions["bank_reference"].apply(_normalise_text)
    )

    invoices["_normalised_currency"] = (
        invoices["currency"].apply(_normalise_text)
    )

    payments["_normalised_currency"] = (
        payments["currency"].apply(_normalise_text)
    )

    bank_transactions["_normalised_currency"] = (
        bank_transactions["currency"].apply(_normalise_text)
    )

    invoices["_numeric_amount"] = pd.to_numeric(
        invoices["invoice_amount"],
        errors="coerce",
    )

    payments["_numeric_amount"] = pd.to_numeric(
        payments["payment_amount"],
        errors="coerce",
    )

    bank_transactions["_numeric_amount"] = pd.to_numeric(
        bank_transactions["transaction_amount"],
        errors="coerce",
    )

    results: list[dict[str, Any]] = []

    for _, invoice in invoices.iterrows():
        invoice_id = str(invoice["invoice_id"])
        invoice_reference = invoice["_normalised_reference"]
        invoice_currency = invoice["_normalised_currency"]
        invoice_amount = invoice["_numeric_amount"]

        if not invoice_reference:
            results.append(
                {
                    "invoice_id": invoice_id,
                    "status": "unmatched",
                    "matching_method": "exact_reference",
                    "confidence_score": 0,
                    "payment_ids": [],
                    "transaction_ids": [],
                    "explanation": (
                        "The invoice has no usable reference, so exact "
                        "reference matching could not be performed."
                    ),
                }
            )
            continue

        payment_candidates = payments[
            payments["_normalised_reference"] == invoice_reference
        ]

        transaction_candidates = bank_transactions[
            bank_transactions["_normalised_reference"]
            == invoice_reference
        ]

        payment_ids = (
            payment_candidates["payment_id"]
            .astype(str)
            .tolist()
        )

        transaction_ids = (
            transaction_candidates["transaction_id"]
            .astype(str)
            .tolist()
        )

        if (
            len(payment_candidates) > 1
            or len(transaction_candidates) > 1
        ):
            results.append(
                {
                    "invoice_id": invoice_id,
                    "status": "duplicate_review",
                    "matching_method": "exact_reference",
                    "confidence_score": 60,
                    "payment_ids": payment_ids,
                    "transaction_ids": transaction_ids,
                    "explanation": (
                        "Multiple records share the same reference. "
                        "Human review is required before confirming a match."
                    ),
                }
            )
            continue

        if (
            len(payment_candidates) == 0
            and len(transaction_candidates) == 0
        ):
            results.append(
                {
                    "invoice_id": invoice_id,
                    "status": "unmatched",
                    "matching_method": "exact_reference",
                    "confidence_score": 0,
                    "payment_ids": [],
                    "transaction_ids": [],
                    "explanation": (
                        "No payment or bank transaction was found with "
                        "the invoice reference."
                    ),
                }
            )
            continue

        if (
            len(payment_candidates) != 1
            or len(transaction_candidates) != 1
        ):
            results.append(
                {
                    "invoice_id": invoice_id,
                    "status": "review",
                    "matching_method": "exact_reference",
                    "confidence_score": 65,
                    "payment_ids": payment_ids,
                    "transaction_ids": transaction_ids,
                    "explanation": (
                        "The invoice reference was found in only one "
                        "financial source. Human review is required."
                    ),
                }
            )
            continue

        payment = payment_candidates.iloc[0]
        transaction = transaction_candidates.iloc[0]

        currencies_match = (
            invoice_currency
            == payment["_normalised_currency"]
            == transaction["_normalised_currency"]
        )

        amounts_match = (
            pd.notna(invoice_amount)
            and pd.notna(payment["_numeric_amount"])
            and pd.notna(transaction["_numeric_amount"])
            and abs(invoice_amount - payment["_numeric_amount"]) <= 0.01
            and abs(invoice_amount - transaction["_numeric_amount"]) <= 0.01
        )

        if currencies_match and amounts_match:
            results.append(
                {
                    "invoice_id": invoice_id,
                    "status": "confirmed",
                    "matching_method": "exact_reference",
                    "confidence_score": 100,
                    "payment_ids": payment_ids,
                    "transaction_ids": transaction_ids,
                    "explanation": (
                        "Invoice, payment and bank transaction have the "
                        "same reference, amount and currency."
                    ),
                }
            )
        else:
            conflicts: list[str] = []

            if not currencies_match:
                conflicts.append("currency")

            if not amounts_match:
                conflicts.append("amount")

            results.append(
                {
                    "invoice_id": invoice_id,
                    "status": "review",
                    "matching_method": "exact_reference",
                    "confidence_score": 70,
                    "payment_ids": payment_ids,
                    "transaction_ids": transaction_ids,
                    "explanation": (
                        "The reference matches, but the following fields "
                        f"conflict: {', '.join(conflicts)}."
                    ),
                }
            )

    status_counts = {
        "confirmed": sum(
            result["status"] == "confirmed"
            for result in results
        ),
        "review": sum(
            result["status"] == "review"
            for result in results
        ),
        "duplicate_review": sum(
            result["status"] == "duplicate_review"
            for result in results
        ),
        "unmatched": sum(
            result["status"] == "unmatched"
            for result in results
        ),
    }

    return {
        "matching_method": "exact_reference",
        "total_invoices": len(results),
        "status_counts": status_counts,
        "results": results,
    }