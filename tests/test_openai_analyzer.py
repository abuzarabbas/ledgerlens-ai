from types import SimpleNamespace
from typing import Any

import pytest

from backend.ai_service import (
    AICandidateContext,
    AIRecommendation,
    AIReconciliationDecision,
)
from backend.openai_analyzer import (
    OpenAIAnalysisError,
    OpenAIAnalyzer,
)


class FakeResponsesClient:
    """
    Fake Responses API used to prevent network calls during tests.
    """

    def __init__(
        self,
        parsed_output: AIReconciliationDecision | None,
    ) -> None:
        self.parsed_output = parsed_output
        self.last_request: dict[str, Any] | None = None

    def parse(
        self,
        **kwargs: Any,
    ) -> SimpleNamespace:
        self.last_request = kwargs

        return SimpleNamespace(
            output_parsed=self.parsed_output
        )


class FakeOpenAIClient:
    """
    Fake OpenAI client exposing a responses property.
    """

    def __init__(
        self,
        parsed_output: AIReconciliationDecision | None,
    ) -> None:
        self.responses = FakeResponsesClient(
            parsed_output=parsed_output
        )


def _create_candidate() -> AICandidateContext:
    """
    Create one uncertain reconciliation candidate.
    """

    return AICandidateContext(
        invoice_id="INV-TEST-001",
        payment_ids=["PAY-TEST-001"],
        transaction_ids=["TXN-TEST-001"],
        deterministic_status="review",
        deterministic_confidence_score=90,
        matching_method=(
            "amount_currency_customer_date"
        ),
        supporting_signals=[
            "currency_match",
            "customer_id_match",
            "amount_within_fallback_tolerance",
        ],
        conflicts=[
            "invoice_amount_difference_15.00",
        ],
        match_details={
            "invoice_amount": 1000.00,
            "payment_amount": 985.00,
        },
    )


def _create_decision() -> AIReconciliationDecision:
    """
    Create one valid structured OpenAI decision.
    """

    return AIReconciliationDecision(
        recommendation=AIRecommendation.SUGGEST_MATCH,
        confidence_score=88,
        explanation=(
            "The customer, currency, sender, and date signals "
            "support the proposed match, but the amount "
            "difference still requires manual investigation."
        ),
        supporting_signals=[
            "currency_match",
            "customer_id_match",
        ],
        conflicts=[
            "invoice_amount_difference_15.00",
        ],
        requires_human_review=True,
    )


def test_openai_analyzer_returns_structured_decision() -> None:
    """
    The analyser should return the parsed Pydantic decision.
    """

    expected_decision = _create_decision()
    fake_client = FakeOpenAIClient(
        parsed_output=expected_decision
    )

    analyzer = OpenAIAnalyzer(
        model_name="gpt-5-mini",
        client=fake_client,
    )

    decision = analyzer.analyze(
        _create_candidate()
    )

    assert decision == expected_decision

    assert (
        decision.recommendation
        == AIRecommendation.SUGGEST_MATCH
    )

    assert decision.confidence_score == 88
    assert decision.requires_human_review is True


def test_openai_analyzer_uses_schema_and_disables_storage() -> None:
    """
    Requests should use the structured schema and disable storage.
    """

    fake_client = FakeOpenAIClient(
        parsed_output=_create_decision()
    )

    analyzer = OpenAIAnalyzer(
        model_name="gpt-5-mini",
        client=fake_client,
    )

    analyzer.analyze(
        _create_candidate()
    )

    request = fake_client.responses.last_request

    assert request is not None
    assert request["model"] == "gpt-5-mini"

    assert (
        request["text_format"]
        is AIReconciliationDecision
    )

    assert request["store"] is False

    user_message = request["input"][1]["content"]

    assert "INV-TEST-001" in user_message
    assert "PAY-TEST-001" in user_message
    assert "TXN-TEST-001" in user_message


def test_openai_analyzer_rejects_missing_parsed_output() -> None:
    """
    Empty or refused model responses must not be accepted.
    """

    fake_client = FakeOpenAIClient(
        parsed_output=None
    )

    analyzer = OpenAIAnalyzer(
        model_name="gpt-5-mini",
        client=fake_client,
    )

    with pytest.raises(
        OpenAIAnalysisError,
        match="did not contain a parsed",
    ):
        analyzer.analyze(
            _create_candidate()
        )


def test_openai_analyzer_requires_api_key_without_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Production mode must reject missing API credentials.
    """

    monkeypatch.setattr(
        "backend.openai_analyzer.load_dotenv",
        lambda: None,
    )

    monkeypatch.delenv(
        "OPENAI_API_KEY",
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="OPENAI_API_KEY",
    ):
        OpenAIAnalyzer()