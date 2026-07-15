import pytest
from pydantic import ValidationError

from backend.ai_service import (
    AICandidateContext,
    AIRecommendation,
    AIReconciliationDecision,
    MockAIAnalyzer,
    analyze_reconciliation_candidates,
    build_ai_candidate_context,
    select_ai_review_candidates,
)


def _create_candidate(
    *,
    invoice_id: str = "INV-TEST-001",
    status: str = "review",
    confidence_score: int = 90,
    payment_ids: list[str] | None = None,
    transaction_ids: list[str] | None = None,
    supporting_signals: list[str] | None = None,
    conflicts: list[str] | None = None,
) -> AICandidateContext:
    """
    Create a reusable AI candidate for unit tests.
    """

    return AICandidateContext(
        invoice_id=invoice_id,
        payment_ids=payment_ids or ["PAY-TEST-001"],
        transaction_ids=transaction_ids or ["TXN-TEST-001"],
        deterministic_status=status,
        deterministic_confidence_score=confidence_score,
        matching_method="amount_currency_customer_date",
        supporting_signals=supporting_signals or [
            "currency_match",
            "customer_id_match",
            "exact_amount_match",
        ],
        conflicts=conflicts or [],
        match_details={},
    )


def test_confirmed_matches_are_excluded_from_ai_review() -> None:
    """
    Deterministically confirmed matches must never be sent to AI.
    """

    matching_result = {
        "results": [
            {
                "invoice_id": "INV-001",
                "status": "confirmed",
                "confidence_score": 100,
                "matching_method": "exact_reference",
                "payment_ids": ["PAY-001"],
                "transaction_ids": ["TXN-001"],
                "supporting_signals": [
                    "exact_reference_match",
                ],
                "conflicts": [],
            },
            {
                "invoice_id": "INV-002",
                "status": "review",
                "confidence_score": 90,
                "matching_method": (
                    "amount_currency_customer_date"
                ),
                "payment_ids": ["PAY-002"],
                "transaction_ids": ["TXN-002"],
                "supporting_signals": [
                    "currency_match",
                ],
                "conflicts": [],
            },
            {
                "invoice_id": "INV-003",
                "status": "duplicate_review",
                "confidence_score": 60,
                "matching_method": "exact_reference",
                "payment_ids": ["PAY-003", "PAY-004"],
                "transaction_ids": ["TXN-003", "TXN-004"],
                "supporting_signals": [
                    "exact_reference_match",
                ],
                "conflicts": [
                    "multiple_records_share_reference",
                ],
            },
            {
                "invoice_id": "INV-004",
                "status": "unmatched",
                "confidence_score": 0,
                "matching_method": "exact_reference",
                "payment_ids": [],
                "transaction_ids": [],
                "supporting_signals": [],
                "conflicts": [
                    "reference_not_found",
                ],
            },
        ]
    }

    candidates = select_ai_review_candidates(
        matching_result
    )

    candidate_invoice_ids = {
        candidate.invoice_id
        for candidate in candidates
    }

    assert candidate_invoice_ids == {
        "INV-002",
        "INV-003",
        "INV-004",
    }

    assert "INV-001" not in candidate_invoice_ids


def test_candidate_context_requires_invoice_id() -> None:
    """
    AI review records without an invoice identifier must be rejected.
    """

    with pytest.raises(
        ValueError,
        match="must contain an invoice_id",
    ):
        build_ai_candidate_context(
            {
                "status": "review",
                "confidence_score": 80,
                "matching_method": "fallback",
                "payment_ids": [],
                "transaction_ids": [],
            }
        )


def test_ai_decision_confidence_cannot_exceed_95() -> None:
    """
    AI confidence must never communicate deterministic certainty.
    """

    with pytest.raises(ValidationError):
        AIReconciliationDecision(
            recommendation=AIRecommendation.SUGGEST_MATCH,
            confidence_score=96,
            explanation=(
                "The candidate appears consistent, but it still "
                "requires human review before acceptance."
            ),
            supporting_signals=[],
            conflicts=[],
            requires_human_review=True,
        )


def test_ai_decision_cannot_disable_human_review() -> None:
    """
    AI output must always require human review.
    """

    with pytest.raises(ValidationError):
        AIReconciliationDecision(
            recommendation=AIRecommendation.SUGGEST_MATCH,
            confidence_score=90,
            explanation=(
                "The candidate appears consistent, but the final "
                "decision must remain under human control."
            ),
            supporting_signals=[],
            conflicts=[],
            requires_human_review=False,
        )


def test_mock_ai_rejects_currency_mismatch() -> None:
    """
    Conflicting currencies should produce a reject recommendation.
    """

    analyzer = MockAIAnalyzer()

    candidate = _create_candidate(
        conflicts=["currency_mismatch"],
    )

    decision = analyzer.analyze(candidate)

    assert (
        decision.recommendation
        == AIRecommendation.REJECT_MATCH
    )

    assert decision.confidence_score == 92
    assert decision.requires_human_review is True
    assert "currency_mismatch" in decision.conflicts


def test_mock_ai_requests_more_information_for_duplicates() -> None:
    """
    Duplicate candidates cannot be resolved automatically.
    """

    analyzer = MockAIAnalyzer()

    candidate = _create_candidate(
        status="duplicate_review",
        confidence_score=60,
        payment_ids=["PAY-001", "PAY-002"],
        transaction_ids=["TXN-001", "TXN-002"],
        conflicts=[
            "multiple_records_share_reference",
        ],
    )

    decision = analyzer.analyze(candidate)

    assert (
        decision.recommendation
        == AIRecommendation.NEEDS_MORE_INFORMATION
    )

    assert decision.confidence_score == 70
    assert decision.requires_human_review is True


def test_mock_ai_suggests_small_amount_difference() -> None:
    """
    A small amount difference may receive a cautious suggestion.
    """

    analyzer = MockAIAnalyzer()

    candidate = _create_candidate(
        confidence_score=90,
        supporting_signals=[
            "currency_match",
            "customer_id_match",
            "strong_sender_name_similarity",
            "amount_within_fallback_tolerance",
            "dates_within_30_days",
        ],
        conflicts=[
            "invoice_amount_difference_15.00",
        ],
    )

    decision = analyzer.analyze(candidate)

    assert (
        decision.recommendation
        == AIRecommendation.SUGGEST_MATCH
    )

    assert decision.confidence_score == 88
    assert decision.requires_human_review is True


def test_mock_ai_caps_strong_fallback_recommendation() -> None:
    """
    Strong fallback recommendations must remain below 100.
    """

    analyzer = MockAIAnalyzer()

    candidate = _create_candidate(
        confidence_score=100,
        conflicts=[],
    )

    decision = analyzer.analyze(candidate)

    assert (
        decision.recommendation
        == AIRecommendation.SUGGEST_MATCH
    )

    assert decision.confidence_score == 95
    assert decision.requires_human_review is True


def test_ai_analysis_summary_counts_only_ambiguous_cases() -> None:
    """
    The analysis summary should exclude confirmed deterministic matches.
    """

    matching_result = {
        "results": [
            {
                "invoice_id": "INV-001",
                "status": "confirmed",
                "confidence_score": 100,
                "matching_method": "exact_reference",
                "payment_ids": ["PAY-001"],
                "transaction_ids": ["TXN-001"],
                "supporting_signals": [
                    "exact_reference_match",
                ],
                "conflicts": [],
            },
            {
                "invoice_id": "INV-002",
                "status": "review",
                "confidence_score": 90,
                "matching_method": (
                    "amount_currency_customer_date"
                ),
                "payment_ids": ["PAY-002"],
                "transaction_ids": ["TXN-002"],
                "supporting_signals": [
                    "currency_match",
                    "customer_id_match",
                ],
                "conflicts": [
                    "invoice_amount_difference_15.00",
                ],
            },
            {
                "invoice_id": "INV-003",
                "status": "review",
                "confidence_score": 70,
                "matching_method": "exact_reference",
                "payment_ids": ["PAY-003"],
                "transaction_ids": ["TXN-003"],
                "supporting_signals": [
                    "exact_reference_match",
                ],
                "conflicts": [
                    "currency_mismatch",
                ],
            },
            {
                "invoice_id": "INV-004",
                "status": "duplicate_review",
                "confidence_score": 60,
                "matching_method": "exact_reference",
                "payment_ids": [
                    "PAY-004",
                    "PAY-005",
                ],
                "transaction_ids": [
                    "TXN-004",
                    "TXN-005",
                ],
                "supporting_signals": [
                    "exact_reference_match",
                ],
                "conflicts": [
                    "multiple_records_share_reference",
                ],
            },
        ]
    }

    analysis_result = analyze_reconciliation_candidates(
        matching_result=matching_result,
        analyzer=MockAIAnalyzer(),
    )

    assert analysis_result["analysis_mode"] == "mock"
    assert (
        analysis_result["model_name"]
        == "deterministic-mock-v1"
    )

    assert analysis_result["total_candidates"] == 3

    assert analysis_result["recommendation_counts"] == {
        "suggest_match": 1,
        "reject_match": 1,
        "needs_more_information": 1,
    }

    analyzed_invoice_ids = {
        decision["invoice_id"]
        for decision in analysis_result["decisions"]
    }

    assert analyzed_invoice_ids == {
        "INV-002",
        "INV-003",
        "INV-004",
    }

    assert "INV-001" not in analyzed_invoice_ids

    for decision_record in analysis_result["decisions"]:
        assert (
            decision_record["decision"][
                "requires_human_review"
            ]
            is True
        )

        assert (
            decision_record["decision"][
                "confidence_score"
            ]
            <= 95
        )