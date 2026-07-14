from typing import Any

import pandas as pd


REQUIRED_EXPECTED_COLUMNS = {
    "invoice_id",
    "payment_id",
    "transaction_id",
    "expected_result",
}

REVIEW_STATUSES = {
    "review",
    "duplicate_review",
}


class ReconciliationEvaluationError(ValueError):
    """Raised when reconciliation evaluation cannot be completed."""


def _clean_identifier(value: Any) -> str | None:
    """
    Convert an identifier into a clean string.

    Missing or empty values return None.
    """

    if pd.isna(value):
        return None

    cleaned_value = str(value).strip()

    if not cleaned_value:
        return None

    return cleaned_value


def _safe_divide(
    numerator: int,
    denominator: int,
) -> float:
    """
    Divide two integers safely and return a rounded result.
    """

    if denominator == 0:
        return 0.0

    return round(numerator / denominator, 4)


def _resolve_expected_status(
    expected_results: set[str],
) -> str:
    """
    Convert ground-truth result labels into system status labels.

    The synthetic ground truth uses detailed business labels such as
    partial and currency_mismatch. The matching engine uses broader
    workflow statuses such as review and duplicate_review.
    """

    normalised_results = {
        result.strip().lower()
        for result in expected_results
        if result and result.strip()
    }

    if "duplicate" in normalised_results:
        return "duplicate_review"

    review_results = {
        "review",
        "partial",
        "currency_mismatch",
    }

    if normalised_results & review_results:
        return "review"

    if "confirmed" in normalised_results:
        return "confirmed"

    if normalised_results == {"unmatched"}:
        return "unmatched"

    raise ReconciliationEvaluationError(
        "Unsupported expected result combination: "
        f"{sorted(normalised_results)}"
    )


def _create_link_tokens(
    payment_ids: set[str],
    transaction_ids: set[str],
) -> set[str]:
    """
    Create typed reconciliation links for metric calculation.

    Prefixes prevent a payment identifier and transaction identifier
    from being treated as the same type of record.
    """

    payment_links = {
        f"payment:{payment_id}"
        for payment_id in payment_ids
    }

    transaction_links = {
        f"transaction:{transaction_id}"
        for transaction_id in transaction_ids
    }

    return payment_links | transaction_links


def evaluate_reconciliation(
    matching_result: dict[str, Any],
    expected_matches: pd.DataFrame,
) -> dict[str, Any]:
    """
    Compare reconciliation results against labelled ground truth.

    Metrics include:

    - Status accuracy
    - Complete-case accuracy
    - Link precision
    - Link recall
    - Link F1 score
    - Confirmed-match precision
    - Manual-review rate
    - Automatic-confirmation rate
    """

    expected_matches = expected_matches.copy()

    expected_matches.columns = [
        str(column).strip()
        for column in expected_matches.columns
    ]

    missing_columns = sorted(
        REQUIRED_EXPECTED_COLUMNS
        - set(expected_matches.columns)
    )

    if missing_columns:
        raise ReconciliationEvaluationError(
            "Expected-match file is missing columns: "
            + ", ".join(missing_columns)
        )

    if expected_matches.empty:
        raise ReconciliationEvaluationError(
            "Expected-match dataset contains no records."
        )

    predicted_results = matching_result.get("results")

    if not isinstance(predicted_results, list):
        raise ReconciliationEvaluationError(
            "Matching result must contain a results list."
        )

    expected_matches["_clean_invoice_id"] = (
        expected_matches["invoice_id"].apply(
            _clean_identifier
        )
    )

    unsupported_rows = expected_matches[
        expected_matches["_clean_invoice_id"].isna()
    ]

    evaluable_expected_matches = expected_matches[
        expected_matches["_clean_invoice_id"].notna()
    ].copy()

    if evaluable_expected_matches.empty:
        raise ReconciliationEvaluationError(
            "No invoice-level expected records are available."
        )

    predicted_by_invoice: dict[str, dict[str, Any]] = {}

    for predicted_result in predicted_results:
        predicted_invoice_id = _clean_identifier(
            predicted_result.get("invoice_id")
        )

        if predicted_invoice_id is None:
            continue

        predicted_by_invoice[predicted_invoice_id] = (
            predicted_result
        )

    expected_invoice_ids = set(
        evaluable_expected_matches[
            "_clean_invoice_id"
        ].astype(str)
    )

    true_positive_links = 0
    false_positive_links = 0
    false_negative_links = 0

    status_correct_count = 0
    complete_case_correct_count = 0
    manual_review_count = 0
    automatic_confirmation_count = 0
    unmatched_prediction_count = 0
    confirmed_prediction_count = 0
    correct_confirmed_prediction_count = 0

    case_results: list[dict[str, Any]] = []

    grouped_expected_matches = (
        evaluable_expected_matches.groupby(
            "_clean_invoice_id",
            sort=True,
        )
    )

    for invoice_id, expected_group in grouped_expected_matches:
        invoice_id = str(invoice_id)

        expected_result_values = {
            str(value).strip().lower()
            for value in expected_group[
                "expected_result"
            ].dropna()
        }

        expected_status = _resolve_expected_status(
            expected_result_values
        )

        expected_payment_ids = {
            payment_id
            for payment_id in (
                _clean_identifier(value)
                for value in expected_group["payment_id"]
            )
            if payment_id is not None
        }

        expected_transaction_ids = {
            transaction_id
            for transaction_id in (
                _clean_identifier(value)
                for value in expected_group[
                    "transaction_id"
                ]
            )
            if transaction_id is not None
        }

        predicted_result = predicted_by_invoice.get(
            invoice_id
        )

        if predicted_result is None:
            predicted_status = "missing_prediction"
            predicted_payment_ids: set[str] = set()
            predicted_transaction_ids: set[str] = set()
            predicted_confidence_score = None
            predicted_matching_method = None
        else:
            predicted_status = str(
                predicted_result.get(
                    "status",
                    "missing_status",
                )
            )

            predicted_payment_ids = {
                payment_id
                for payment_id in (
                    _clean_identifier(value)
                    for value in predicted_result.get(
                        "payment_ids",
                        [],
                    )
                )
                if payment_id is not None
            }

            predicted_transaction_ids = {
                transaction_id
                for transaction_id in (
                    _clean_identifier(value)
                    for value in predicted_result.get(
                        "transaction_ids",
                        [],
                    )
                )
                if transaction_id is not None
            }

            predicted_confidence_score = (
                predicted_result.get(
                    "confidence_score"
                )
            )

            predicted_matching_method = (
                predicted_result.get(
                    "matching_method"
                )
            )

        expected_links = _create_link_tokens(
            payment_ids=expected_payment_ids,
            transaction_ids=expected_transaction_ids,
        )

        predicted_links = _create_link_tokens(
            payment_ids=predicted_payment_ids,
            transaction_ids=predicted_transaction_ids,
        )

        true_positive_count = len(
            expected_links & predicted_links
        )

        false_positive_count = len(
            predicted_links - expected_links
        )

        false_negative_count = len(
            expected_links - predicted_links
        )

        true_positive_links += true_positive_count
        false_positive_links += false_positive_count
        false_negative_links += false_negative_count

        status_correct = (
            predicted_status == expected_status
        )

        links_exact = (
            predicted_links == expected_links
        )

        complete_case_correct = (
            status_correct and links_exact
        )

        if status_correct:
            status_correct_count += 1

        if complete_case_correct:
            complete_case_correct_count += 1

        if predicted_status in REVIEW_STATUSES:
            manual_review_count += 1

        if predicted_status == "confirmed":
            automatic_confirmation_count += 1
            confirmed_prediction_count += 1

            if complete_case_correct:
                correct_confirmed_prediction_count += 1

        if predicted_status == "unmatched":
            unmatched_prediction_count += 1

        case_results.append(
            {
                "invoice_id": invoice_id,
                "expected_status": expected_status,
                "predicted_status": predicted_status,
                "status_correct": status_correct,
                "links_exact": links_exact,
                "complete_case_correct": (
                    complete_case_correct
                ),
                "expected_payment_ids": sorted(
                    expected_payment_ids
                ),
                "predicted_payment_ids": sorted(
                    predicted_payment_ids
                ),
                "expected_transaction_ids": sorted(
                    expected_transaction_ids
                ),
                "predicted_transaction_ids": sorted(
                    predicted_transaction_ids
                ),
                "true_positive_links": (
                    true_positive_count
                ),
                "false_positive_links": (
                    false_positive_count
                ),
                "false_negative_links": (
                    false_negative_count
                ),
                "confidence_score": (
                    predicted_confidence_score
                ),
                "matching_method": (
                    predicted_matching_method
                ),
            }
        )

    total_evaluated_invoices = len(case_results)

    link_precision = _safe_divide(
        true_positive_links,
        true_positive_links + false_positive_links,
    )

    link_recall = _safe_divide(
        true_positive_links,
        true_positive_links + false_negative_links,
    )

    if link_precision + link_recall == 0:
        link_f1_score = 0.0
    else:
        link_f1_score = round(
            (
                2
                * link_precision
                * link_recall
                / (link_precision + link_recall)
            ),
            4,
        )

    extra_prediction_invoice_ids = sorted(
        set(predicted_by_invoice)
        - expected_invoice_ids
    )

    notes: list[str] = []

    if len(unsupported_rows) > 0:
        notes.append(
            f"{len(unsupported_rows)} expected row(s) were "
            "excluded because they do not contain an invoice_id. "
            "These represent orphan-record cases that require a "
            "separate transaction-level evaluation."
        )

    if extra_prediction_invoice_ids:
        notes.append(
            "Predictions were returned for invoice IDs not present "
            "in the expected dataset."
        )

    return {
        "evaluation_scope": {
            "expected_rows": int(len(expected_matches)),
            "evaluated_invoices": (
                total_evaluated_invoices
            ),
            "unsupported_rows_without_invoice_id": int(
                len(unsupported_rows)
            ),
            "extra_prediction_invoice_ids": (
                extra_prediction_invoice_ids
            ),
        },
        "metrics": {
            "status_accuracy": _safe_divide(
                status_correct_count,
                total_evaluated_invoices,
            ),
            "complete_case_accuracy": _safe_divide(
                complete_case_correct_count,
                total_evaluated_invoices,
            ),
            "link_precision": link_precision,
            "link_recall": link_recall,
            "link_f1_score": link_f1_score,
            "confirmed_match_precision": _safe_divide(
                correct_confirmed_prediction_count,
                confirmed_prediction_count,
            ),
            "manual_review_rate": _safe_divide(
                manual_review_count,
                total_evaluated_invoices,
            ),
            "automatic_confirmation_rate": (
                _safe_divide(
                    automatic_confirmation_count,
                    total_evaluated_invoices,
                )
            ),
            "unmatched_prediction_rate": _safe_divide(
                unmatched_prediction_count,
                total_evaluated_invoices,
            ),
        },
        "link_counts": {
            "true_positive": true_positive_links,
            "false_positive": false_positive_links,
            "false_negative": false_negative_links,
        },
        "case_results": case_results,
        "notes": notes,
    }