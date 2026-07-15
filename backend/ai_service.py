from enum import StrEnum
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


AI_REVIEW_STATUSES = {
    "review",
    "duplicate_review",
    "unmatched",
}


class AIRecommendation(StrEnum):
    """
    Supported AI recommendation types.

    AI recommendations never make final financial decisions.
    """

    SUGGEST_MATCH = "suggest_match"
    REJECT_MATCH = "reject_match"
    NEEDS_MORE_INFORMATION = "needs_more_information"


class AICandidateContext(BaseModel):
    """
    Deterministic reconciliation information supplied to an AI analyser.
    """

    model_config = ConfigDict(extra="forbid")

    invoice_id: str
    payment_ids: list[str] = Field(default_factory=list)
    transaction_ids: list[str] = Field(default_factory=list)

    deterministic_status: str
    deterministic_confidence_score: int = Field(
        ge=0,
        le=100,
    )
    matching_method: str

    supporting_signals: list[str] = Field(
        default_factory=list
    )
    conflicts: list[str] = Field(default_factory=list)
    match_details: dict[str, Any] = Field(
        default_factory=dict
    )


class AIReconciliationDecision(BaseModel):
    """
    Structured output expected from an AI reconciliation analyser.

    AI confidence is capped at 95 because only deterministic,
    rule-confirmed matches may receive a confidence score of 100.
    """

    model_config = ConfigDict(extra="forbid")

    recommendation: AIRecommendation

    confidence_score: int = Field(
        ge=0,
        le=95,
    )

    explanation: str = Field(
        min_length=20,
        max_length=1000,
    )

    supporting_signals: list[str] = Field(
        default_factory=list
    )

    conflicts: list[str] = Field(default_factory=list)

    requires_human_review: Literal[True] = True


class AIAnalysisRecord(BaseModel):
    """
    Complete AI analysis record stored for one invoice candidate.
    """

    model_config = ConfigDict(extra="forbid")

    invoice_id: str
    payment_ids: list[str]
    transaction_ids: list[str]

    deterministic_status: str
    deterministic_confidence_score: int

    provider: str
    model_name: str

    decision: AIReconciliationDecision


@runtime_checkable
class AIAnalyzer(Protocol):
    """
    Interface implemented by mock and production AI analysers.
    """

    provider: str
    model_name: str

    def analyze(
        self,
        candidate: AICandidateContext,
    ) -> AIReconciliationDecision:
        """
        Analyse one ambiguous reconciliation candidate.
        """
        ...


def _normalise_string_list(value: Any) -> list[str]:
    """
    Convert an unknown value into a clean list of strings.
    """

    if not isinstance(value, list):
        return []

    return [
        str(item).strip()
        for item in value
        if item is not None and str(item).strip()
    ]


def build_ai_candidate_context(
    reconciliation_result: dict[str, Any],
) -> AICandidateContext:
    """
    Convert one deterministic result into an AI candidate context.
    """

    invoice_id = reconciliation_result.get("invoice_id")

    if invoice_id is None or not str(invoice_id).strip():
        raise ValueError(
            "AI review candidates must contain an invoice_id."
        )

    confidence_score = reconciliation_result.get(
        "confidence_score",
        0,
    )

    try:
        confidence_score = int(confidence_score)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "The deterministic confidence score must be an integer."
        ) from error

    match_details = reconciliation_result.get(
        "match_details",
        {},
    )

    if not isinstance(match_details, dict):
        match_details = {}

    return AICandidateContext(
        invoice_id=str(invoice_id).strip(),
        payment_ids=_normalise_string_list(
            reconciliation_result.get("payment_ids")
        ),
        transaction_ids=_normalise_string_list(
            reconciliation_result.get("transaction_ids")
        ),
        deterministic_status=str(
            reconciliation_result.get(
                "status",
                "unknown",
            )
        ),
        deterministic_confidence_score=confidence_score,
        matching_method=str(
            reconciliation_result.get(
                "matching_method",
                "unknown",
            )
        ),
        supporting_signals=_normalise_string_list(
            reconciliation_result.get(
                "supporting_signals"
            )
        ),
        conflicts=_normalise_string_list(
            reconciliation_result.get("conflicts")
        ),
        match_details=match_details,
    )


def select_ai_review_candidates(
    matching_result: dict[str, Any],
) -> list[AICandidateContext]:
    """
    Select only uncertain reconciliation cases for AI analysis.

    Confirmed deterministic matches are excluded.
    """

    reconciliation_results = matching_result.get("results")

    if not isinstance(reconciliation_results, list):
        raise ValueError(
            "The matching result must contain a results list."
        )

    candidates: list[AICandidateContext] = []

    for reconciliation_result in reconciliation_results:
        if not isinstance(reconciliation_result, dict):
            continue

        status = str(
            reconciliation_result.get(
                "status",
                "",
            )
        )

        if status not in AI_REVIEW_STATUSES:
            continue

        candidates.append(
            build_ai_candidate_context(
                reconciliation_result
            )
        )

    return candidates


class MockAIAnalyzer:
    """
    Deterministic substitute for an external AI model.

    The mock analyser enables development and testing without:

    - An API key
    - Network access
    - Usage charges
    - Non-deterministic responses
    """

    provider = "mock"
    model_name = "deterministic-mock-v1"

    def analyze(
        self,
        candidate: AICandidateContext,
    ) -> AIReconciliationDecision:
        """
        Produce a predictable recommendation from deterministic signals.
        """

        conflicts = set(candidate.conflicts)
        signals = list(candidate.supporting_signals)

        if "multiple_records_share_reference" in conflicts:
            return AIReconciliationDecision(
                recommendation=(
                    AIRecommendation.NEEDS_MORE_INFORMATION
                ),
                confidence_score=70,
                explanation=(
                    "Several payment or bank records share the same "
                    "reference. The available evidence does not identify "
                    "one unique match, so a person must inspect the "
                    "duplicate records."
                ),
                supporting_signals=signals,
                conflicts=sorted(conflicts),
                requires_human_review=True,
            )

        if "currency_mismatch" in conflicts:
            return AIReconciliationDecision(
                recommendation=AIRecommendation.REJECT_MATCH,
                confidence_score=92,
                explanation=(
                    "The records use conflicting currencies. A financial "
                    "match should not be accepted until the currency "
                    "difference is investigated and resolved."
                ),
                supporting_signals=signals,
                conflicts=sorted(conflicts),
                requires_human_review=True,
            )

        if "amount_mismatch" in conflicts:
            return AIReconciliationDecision(
                recommendation=(
                    AIRecommendation.NEEDS_MORE_INFORMATION
                ),
                confidence_score=78,
                explanation=(
                    "The reference is consistent, but the invoice and "
                    "payment amounts differ. This may represent a partial "
                    "payment, fee deduction, or incorrect transaction, "
                    "so additional review is required."
                ),
                supporting_signals=signals,
                conflicts=sorted(conflicts),
                requires_human_review=True,
            )

        amount_difference_conflicts = {
            conflict
            for conflict in conflicts
            if conflict.startswith(
                "invoice_amount_difference_"
            )
        }

        if amount_difference_conflicts:
            return AIReconciliationDecision(
                recommendation=AIRecommendation.SUGGEST_MATCH,
                confidence_score=88,
                explanation=(
                    "The amount differs slightly, but currency, customer "
                    "information, sender identity, payment consistency, "
                    "and transaction dates support the proposed match. "
                    "The difference should still be reviewed manually."
                ),
                supporting_signals=signals,
                conflicts=sorted(conflicts),
                requires_human_review=True,
            )

        if (
            candidate.deterministic_confidence_score >= 85
            and candidate.payment_ids
            and candidate.transaction_ids
        ):
            return AIReconciliationDecision(
                recommendation=AIRecommendation.SUGGEST_MATCH,
                confidence_score=min(
                    candidate.deterministic_confidence_score,
                    95,
                ),
                explanation=(
                    "The deterministic engine found a strong candidate "
                    "using consistent amount, currency, customer, sender, "
                    "and date signals. The recommendation remains subject "
                    "to human approval because it was not confirmed by an "
                    "exact reference match."
                ),
                supporting_signals=signals,
                conflicts=sorted(conflicts),
                requires_human_review=True,
            )

        return AIReconciliationDecision(
            recommendation=(
                AIRecommendation.NEEDS_MORE_INFORMATION
            ),
            confidence_score=60,
            explanation=(
                "The available reconciliation signals are insufficient "
                "to support or reject a specific match. Additional source "
                "information or manual investigation is required."
            ),
            supporting_signals=signals,
            conflicts=sorted(conflicts),
            requires_human_review=True,
        )


def analyze_reconciliation_candidates(
    matching_result: dict[str, Any],
    analyzer: AIAnalyzer,
) -> dict[str, Any]:
    """
    Analyse all ambiguous reconciliation candidates.

    Deterministically confirmed records are never sent for AI review.
    """

    candidates = select_ai_review_candidates(
        matching_result
    )

    recommendation_counts = {
        recommendation.value: 0
        for recommendation in AIRecommendation
    }

    analysis_records: list[dict[str, Any]] = []

    for candidate in candidates:
        decision = analyzer.analyze(candidate)

        recommendation_counts[
            decision.recommendation.value
        ] += 1

        record = AIAnalysisRecord(
            invoice_id=candidate.invoice_id,
            payment_ids=candidate.payment_ids,
            transaction_ids=candidate.transaction_ids,
            deterministic_status=(
                candidate.deterministic_status
            ),
            deterministic_confidence_score=(
                candidate.deterministic_confidence_score
            ),
            provider=analyzer.provider,
            model_name=analyzer.model_name,
            decision=decision,
        )

        analysis_records.append(
            record.model_dump(mode="json")
        )

    return {
        "analysis_mode": analyzer.provider,
        "model_name": analyzer.model_name,
        "total_candidates": len(candidates),
        "recommendation_counts": recommendation_counts,
        "decisions": analysis_records,
    }