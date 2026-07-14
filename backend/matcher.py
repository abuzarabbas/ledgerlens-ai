from difflib import SequenceMatcher
from typing import Any

import pandas as pd


AMOUNT_TOLERANCE_PERCENT = 0.01
MINIMUM_AMOUNT_TOLERANCE = 20.00
MAXIMUM_DATE_DISTANCE_DAYS = 45
FALLBACK_REVIEW_THRESHOLD = 85
FALLBACK_MAX_CONFIDENCE = 95
FALLBACK_MAX_CONFIDENCE_WITH_CONFLICT = 90


def _normalise_text(value: Any) -> str:
    """
    Convert a value into a clean uppercase string.

    Missing values become an empty string.
    """

    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def _text_similarity(first_value: Any, second_value: Any) -> float:
    """
    Calculate text similarity between zero and one.
    """

    first_text = _normalise_text(first_value)
    second_text = _normalise_text(second_value)

    if not first_text or not second_text:
        return 0.0

    return SequenceMatcher(
        None,
        first_text,
        second_text,
        autojunk=False,
    ).ratio()


def _parse_amount(value: Any) -> float | None:
    """
    Convert an amount into a float.

    Invalid or missing values return None.
    """

    amount = pd.to_numeric(value, errors="coerce")

    if pd.isna(amount):
        return None

    return float(amount)


def _parse_date(value: Any) -> pd.Timestamp | None:
    """
    Convert a date value into a pandas Timestamp.

    Invalid or missing values return None.
    """

    parsed_date = pd.to_datetime(value, errors="coerce")

    if pd.isna(parsed_date):
        return None

    return parsed_date


def _date_distance_days(
    first_date: Any,
    second_date: Any,
) -> int | None:
    """
    Return the absolute number of days between two dates.
    """

    parsed_first_date = _parse_date(first_date)
    parsed_second_date = _parse_date(second_date)

    if parsed_first_date is None or parsed_second_date is None:
        return None

    return abs((parsed_second_date - parsed_first_date).days)


def _prepare_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy with clean column names.
    """

    prepared = dataframe.copy()

    prepared.columns = [
        str(column).strip()
        for column in prepared.columns
    ]

    return prepared


def _calculate_status_counts(
    results: list[dict[str, Any]],
) -> dict[str, int]:
    """
    Count each reconciliation status.
    """

    supported_statuses = [
        "confirmed",
        "review",
        "duplicate_review",
        "unmatched",
    ]

    return {
        reconciliation_status: sum(
            result["status"] == reconciliation_status
            for result in results
        )
        for reconciliation_status in supported_statuses
    }


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
                    "supporting_signals": [],
                    "conflicts": ["missing_invoice_reference"],
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
                    "supporting_signals": [
                        "exact_reference_match",
                    ],
                    "conflicts": [
                        "multiple_records_share_reference",
                    ],
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
                    "supporting_signals": [],
                    "conflicts": [
                        "reference_not_found",
                    ],
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
                    "supporting_signals": [
                        "invoice_reference_found",
                    ],
                    "conflicts": [
                        "reference_found_in_only_one_source",
                    ],
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
            and abs(
                float(invoice_amount)
                - float(payment["_numeric_amount"])
            ) <= 0.01
            and abs(
                float(invoice_amount)
                - float(transaction["_numeric_amount"])
            ) <= 0.01
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
                    "supporting_signals": [
                        "exact_reference_match",
                        "exact_amount_match",
                        "currency_match",
                    ],
                    "conflicts": [],
                    "explanation": (
                        "Invoice, payment and bank transaction have the "
                        "same reference, amount and currency."
                    ),
                }
            )
        else:
            conflicts: list[str] = []

            if not currencies_match:
                conflicts.append("currency_mismatch")

            if not amounts_match:
                conflicts.append("amount_mismatch")

            results.append(
                {
                    "invoice_id": invoice_id,
                    "status": "review",
                    "matching_method": "exact_reference",
                    "confidence_score": 70,
                    "payment_ids": payment_ids,
                    "transaction_ids": transaction_ids,
                    "supporting_signals": [
                        "exact_reference_match",
                    ],
                    "conflicts": conflicts,
                    "explanation": (
                        "The reference matches, but the following fields "
                        f"conflict: {', '.join(conflicts)}."
                    ),
                }
            )

    return {
        "matching_method": "exact_reference",
        "total_invoices": len(results),
        "status_counts": _calculate_status_counts(results),
        "results": results,
    }


def _score_fallback_pair(
    invoice: pd.Series,
    payment: pd.Series,
    bank_transaction: pd.Series,
) -> dict[str, Any] | None:
    """
    Score a possible invoice, payment and bank-transaction combination.

    A candidate is rejected immediately when currency, amount or date
    conditions are outside the permitted range.
    """

    invoice_amount = _parse_amount(invoice["invoice_amount"])
    payment_amount = _parse_amount(payment["payment_amount"])
    transaction_amount = _parse_amount(
        bank_transaction["transaction_amount"]
    )

    if (
        invoice_amount is None
        or payment_amount is None
        or transaction_amount is None
    ):
        return None

    invoice_currency = _normalise_text(invoice["currency"])
    payment_currency = _normalise_text(payment["currency"])
    transaction_currency = _normalise_text(
        bank_transaction["currency"]
    )

    currencies_match = (
        bool(invoice_currency)
        and invoice_currency
        == payment_currency
        == transaction_currency
    )

    if not currencies_match:
        return None

    amount_tolerance = max(
        MINIMUM_AMOUNT_TOLERANCE,
        invoice_amount * AMOUNT_TOLERANCE_PERCENT,
    )

    invoice_payment_difference = abs(
        invoice_amount - payment_amount
    )

    invoice_transaction_difference = abs(
        invoice_amount - transaction_amount
    )

    payment_transaction_difference = abs(
        payment_amount - transaction_amount
    )

    if (
        invoice_payment_difference > amount_tolerance
        or invoice_transaction_difference > amount_tolerance
        or payment_transaction_difference > 0.01
    ):
        return None

    payment_date_distance = _date_distance_days(
        invoice["invoice_date"],
        payment["payment_date"],
    )

    transaction_date_distance = _date_distance_days(
        invoice["invoice_date"],
        bank_transaction["booking_date"],
    )

    if (
        payment_date_distance is None
        or transaction_date_distance is None
        or payment_date_distance > MAXIMUM_DATE_DISTANCE_DAYS
        or transaction_date_distance > MAXIMUM_DATE_DISTANCE_DAYS
    ):
        return None

    invoice_customer_id = _normalise_text(
        invoice["customer_id"]
    )

    payment_customer_id = _normalise_text(
        payment["customer_id"]
    )

    customer_id_match = (
        bool(invoice_customer_id)
        and invoice_customer_id == payment_customer_id
    )

    sender_name_similarity = _text_similarity(
        invoice["customer_name"],
        bank_transaction["sender_name"],
    )

    description_similarity = _text_similarity(
        invoice["customer_name"],
        payment["payment_description"],
    )

    score = 0
    supporting_signals: list[str] = []
    conflicts: list[str] = []

    score += 15
    supporting_signals.append("currency_match")

    if customer_id_match:
        score += 25
        supporting_signals.append("customer_id_match")
    else:
        conflicts.append("customer_id_not_confirmed")

    sender_score = round(sender_name_similarity * 25)
    score += sender_score

    if sender_name_similarity >= 0.80:
        supporting_signals.append("strong_sender_name_similarity")
    elif sender_name_similarity >= 0.60:
        supporting_signals.append("moderate_sender_name_similarity")
    else:
        conflicts.append("weak_sender_name_similarity")

    if description_similarity >= 0.60:
        score += 5
        supporting_signals.append(
            "payment_description_customer_similarity"
        )

    exact_invoice_amount = (
        invoice_payment_difference <= 0.01
        and invoice_transaction_difference <= 0.01
    )

    if exact_invoice_amount:
        score += 25
        supporting_signals.append("exact_amount_match")
    else:
        score += 18
        supporting_signals.append(
            "amount_within_fallback_tolerance"
        )
        conflicts.append(
            f"invoice_amount_difference_{invoice_payment_difference:.2f}"
        )

    if (
        payment_date_distance <= 30
        and transaction_date_distance <= 30
    ):
        score += 10
        supporting_signals.append("dates_within_30_days")
    else:
        score += 6
        supporting_signals.append("dates_within_45_days")

    score += 5
    supporting_signals.append(
        "payment_and_bank_amount_consistent"
    )

    raw_confidence_score = min(int(score), 100)

    if conflicts:
        confidence_score = min(
            raw_confidence_score,
            FALLBACK_MAX_CONFIDENCE_WITH_CONFLICT,
        )
    else:
        confidence_score = min(
            raw_confidence_score,
            FALLBACK_MAX_CONFIDENCE,
        )

    return {
        "confidence_score": confidence_score,
        "supporting_signals": supporting_signals,
        "conflicts": conflicts,
        "sender_name_similarity": round(
            sender_name_similarity,
            3,
        ),
        "description_similarity": round(
            description_similarity,
            3,
        ),
        "invoice_payment_difference": round(
            invoice_payment_difference,
            2,
        ),
        "invoice_transaction_difference": round(
            invoice_transaction_difference,
            2,
        ),
        "payment_date_distance_days": payment_date_distance,
        "transaction_date_distance_days": (
            transaction_date_distance
        ),
    }


def match_with_fallbacks(
    invoices: pd.DataFrame,
    payments: pd.DataFrame,
    bank_transactions: pd.DataFrame,
) -> dict[str, Any]:
    """
    Run exact-reference matching followed by fallback matching.

    Fallback matching is attempted only for invoices that remain
    unmatched after exact-reference matching.
    """

    invoices = _prepare_dataframe(invoices)
    payments = _prepare_dataframe(payments)
    bank_transactions = _prepare_dataframe(bank_transactions)

    exact_result = match_exact_references(
        invoices=invoices,
        payments=payments,
        bank_transactions=bank_transactions,
    )

    results = exact_result["results"]

    used_payment_ids: set[str] = set()
    used_transaction_ids: set[str] = set()

    for result in results:
        if result["status"] == "unmatched":
            continue

        used_payment_ids.update(
            str(payment_id)
            for payment_id in result["payment_ids"]
        )

        used_transaction_ids.update(
            str(transaction_id)
            for transaction_id in result["transaction_ids"]
        )

    final_results: list[dict[str, Any]] = []

    for exact_match in results:
        if exact_match["status"] != "unmatched":
            final_results.append(exact_match)
            continue

        invoice_id = str(exact_match["invoice_id"])

        invoice_rows = invoices[
            invoices["invoice_id"].astype(str) == invoice_id
        ]

        if invoice_rows.empty:
            final_results.append(exact_match)
            continue

        invoice = invoice_rows.iloc[0]

        available_payments = payments[
            ~payments["payment_id"]
            .astype(str)
            .isin(used_payment_ids)
        ]

        available_transactions = bank_transactions[
            ~bank_transactions["transaction_id"]
            .astype(str)
            .isin(used_transaction_ids)
        ]

        best_candidate: dict[str, Any] | None = None

        for _, payment in available_payments.iterrows():
            for _, transaction in available_transactions.iterrows():
                candidate_score = _score_fallback_pair(
                    invoice=invoice,
                    payment=payment,
                    bank_transaction=transaction,
                )

                if candidate_score is None:
                    continue

                candidate = {
                    "payment_id": str(payment["payment_id"]),
                    "transaction_id": str(
                        transaction["transaction_id"]
                    ),
                    **candidate_score,
                }

                if (
                    best_candidate is None
                    or candidate["confidence_score"]
                    > best_candidate["confidence_score"]
                ):
                    best_candidate = candidate

        if (
            best_candidate is None
            or best_candidate["confidence_score"]
            < FALLBACK_REVIEW_THRESHOLD
        ):
            final_results.append(exact_match)
            continue

        payment_id = best_candidate["payment_id"]
        transaction_id = best_candidate["transaction_id"]

        used_payment_ids.add(payment_id)
        used_transaction_ids.add(transaction_id)

        final_results.append(
            {
                "invoice_id": invoice_id,
                "status": "review",
                "matching_method": (
                    "amount_currency_customer_date"
                ),
                "confidence_score": (
                    best_candidate["confidence_score"]
                ),
                "payment_ids": [payment_id],
                "transaction_ids": [transaction_id],
                "supporting_signals": (
                    best_candidate["supporting_signals"]
                ),
                "conflicts": best_candidate["conflicts"],
                "match_details": {
                    "sender_name_similarity": (
                        best_candidate[
                            "sender_name_similarity"
                        ]
                    ),
                    "description_similarity": (
                        best_candidate[
                            "description_similarity"
                        ]
                    ),
                    "invoice_payment_difference": (
                        best_candidate[
                            "invoice_payment_difference"
                        ]
                    ),
                    "invoice_transaction_difference": (
                        best_candidate[
                            "invoice_transaction_difference"
                        ]
                    ),
                    "payment_date_distance_days": (
                        best_candidate[
                            "payment_date_distance_days"
                        ]
                    ),
                    "transaction_date_distance_days": (
                        best_candidate[
                            "transaction_date_distance_days"
                        ]
                    ),
                },
                "explanation": (
                    "No complete exact-reference match was available. "
                    "The payment and bank transaction are suggested "
                    "because their amount, currency, customer information "
                    "and dates are sufficiently consistent. Human review "
                    "is required."
                ),
            }
        )

    return {
        "matching_method": (
            "exact_reference_then_amount_currency_customer_date"
        ),
        "total_invoices": len(final_results),
        "status_counts": _calculate_status_counts(
            final_results
        ),
        "results": final_results,
    }