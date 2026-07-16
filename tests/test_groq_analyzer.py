from types import SimpleNamespace
from typing import Any

import pytest

from backend.ai_service import (
    AICandidateContext,
    AIRecommendation,
    AIReconciliationDecision,
)
from backend.groq_analyzer import (
    GROQ_DECISION_SCHEMA,
    GroqAnalysisError,
    GroqAnalyzer,
)


class FakeChatCompletions:
    """
    Fake Groq chat-completions resource.

    It stores the request and returns a predefined response without
    accessing the network.
    """

    def __init__(
        self,
        content: str | None,
    ) -> None:
        self.content = content
        self.last_request: dict[str, Any] | None = None

    def create(
        self,
        **kwargs: Any,
    ) -> SimpleNamespace:
        self.last_request = kwargs

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=self.content
                    )
                )
            ]
        )


class FakeGroqClient:
    """
    Fake Groq client exposing chat.completions.create.
    """

    def __init__(
        self,
        content: str | None,
    ) -> None:
        self.completions = FakeChatCompletions(
            content=content
        )

        self.chat = SimpleNamespace(
            completions=self.completions
        )


def _create_candidate() -> AICandidateContext:
    """
    Create one uncertain reconciliation candidate.
    """

    return AICandidateContext(
        invoice_id="INV-GROQ-001",
        payment_ids=["PAY-GROQ-001"],
        transaction_ids=["TXN-GROQ-001"],
        deterministic_status="review",
        deterministic_confidence_score=90,
        matching_method=(
            "amount_currency_customer_date"
        ),
        supporting_signals=[
            "currency_match",
            "customer_id_match",
            "strong_sender_name_similarity",
            "dates_within_30_days",
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
    Create one valid structured Groq decision.
    """

    return AIReconciliationDecision(
        recommendation=AIRecommendation.SUGGEST_MATCH,
        confidence_score=88,
        explanation=(
            "The currency, customer, sender, and date signals "
            "support the proposed match, but the amount "
            "difference still requires manual investigation."
        ),
        supporting_signals=[
            "currency_match",
            "customer_id_match",
            "strong_sender_name_similarity",
            "dates_within_30_days",
        ],
        conflicts=[
            "invoice_amount_difference_15.00",
        ],
        requires_human_review=True,
    )


def test_groq_analyzer_returns_structured_decision() -> None:
    """
    The analyser should return a validated Pydantic decision.
    """

    expected_decision = _create_decision()

    fake_client = FakeGroqClient(
        content=expected_decision.model_dump_json()
    )

    analyzer = GroqAnalyzer(
        model_name="openai/gpt-oss-20b",
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


def test_groq_analyzer_uses_strict_json_schema() -> None:
    """
    Groq requests must use strict structured output.
    """

    fake_client = FakeGroqClient(
        content=_create_decision().model_dump_json()
    )

    analyzer = GroqAnalyzer(
        model_name="openai/gpt-oss-20b",
        client=fake_client,
    )

    analyzer.analyze(
        _create_candidate()
    )

    request = fake_client.completions.last_request

    assert request is not None
    assert request["model"] == "openai/gpt-oss-20b"

    response_format = request["response_format"]

    assert response_format["type"] == "json_schema"

    json_schema = response_format["json_schema"]

    assert json_schema["strict"] is True

    assert (
        json_schema["schema"]
        == GROQ_DECISION_SCHEMA
    )

    assert (
        json_schema["schema"][
            "additionalProperties"
        ]
        is False
    )

    assert set(
        json_schema["schema"]["required"]
    ) == set(
        json_schema["schema"]["properties"].keys()
    )


def test_groq_request_contains_candidate_identifiers() -> None:
    """
    The candidate identifiers must be included in the model request.
    """

    fake_client = FakeGroqClient(
        content=_create_decision().model_dump_json()
    )

    analyzer = GroqAnalyzer(
        model_name="openai/gpt-oss-20b",
        client=fake_client,
    )

    analyzer.analyze(
        _create_candidate()
    )

    request = fake_client.completions.last_request

    assert request is not None

    user_message = request["messages"][1]["content"]

    assert "INV-GROQ-001" in user_message
    assert "PAY-GROQ-001" in user_message
    assert "TXN-GROQ-001" in user_message


def test_groq_analyzer_rejects_empty_response() -> None:
    """
    Empty Groq responses must never be accepted.
    """

    fake_client = FakeGroqClient(
        content=None
    )

    analyzer = GroqAnalyzer(
        model_name="openai/gpt-oss-20b",
        client=fake_client,
    )

    with pytest.raises(
        GroqAnalysisError,
        match="empty reconciliation decision",
    ):
        analyzer.analyze(
            _create_candidate()
        )


def test_groq_analyzer_rejects_invalid_json() -> None:
    """
    Invalid JSON must never enter the reconciliation workflow.
    """

    fake_client = FakeGroqClient(
        content="This is not JSON."
    )

    analyzer = GroqAnalyzer(
        model_name="openai/gpt-oss-20b",
        client=fake_client,
    )

    with pytest.raises(
        GroqAnalysisError,
        match="invalid reconciliation decision",
    ):
        analyzer.analyze(
            _create_candidate()
        )


def test_groq_analyzer_requires_api_key_without_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Production mode must reject missing Groq credentials.
    """

    monkeypatch.setattr(
        "backend.groq_analyzer.load_dotenv",
        lambda: None,
    )

    monkeypatch.delenv(
        "GROQ_API_KEY",
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="GROQ_API_KEY",
    ):
        GroqAnalyzer()