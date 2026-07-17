import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import APIError, Groq
from pydantic import ValidationError

from backend.ai_service import (
    AICandidateContext,
    AIReconciliationDecision,
)


SYSTEM_INSTRUCTIONS = """
You are a financial reconciliation review assistant.

You assess one reconciliation candidate produced by a deterministic
matching engine.

Rules:

1. Use only the information supplied in the candidate.
2. Never invent invoice, payment, transaction, customer, or reference IDs.
3. Never describe a recommendation as a final accounting decision.
4. Every recommendation must require human review.
5. Confidence must remain between 0 and 95.
6. Use suggest_match only when the evidence strongly supports the match.
7. Use reject_match when there is a material contradiction, such as a
   currency mismatch.
8. Use needs_more_information when evidence is incomplete, duplicated,
   conflicting, or insufficient.
9. Include the most relevant supporting signals and conflicts.
10. Keep the explanation factual, concise, and suitable for an audit trail.
""".strip()


GROQ_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "recommendation": {
            "type": "string",
            "enum": [
                "suggest_match",
                "reject_match",
                "needs_more_information",
            ],
        },
        "confidence_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 95,
        },
        "explanation": {
            "type": "string",
        },
        "supporting_signals": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "conflicts": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "requires_human_review": {
            "type": "boolean",
            "enum": [True],
        },
    },
    "required": [
        "recommendation",
        "confidence_score",
        "explanation",
        "supporting_signals",
        "conflicts",
        "requires_human_review",
    ],
    "additionalProperties": False,
}


class GroqAnalysisError(RuntimeError):
    """
    Raised when Groq cannot complete a reconciliation analysis.
    """


class GroqAnalyzer:
    """
    Production reconciliation analyser backed by Groq.

    The analyser implements the same interface as MockAIAnalyzer.
    """

    provider = "groq"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        client: Any | None = None,
    ) -> None:
        """
        Configure the Groq analyser.

        A fake client can be injected during automated tests so that
        tests never make external API calls.
        """

        load_dotenv()

        self.model_name = (
            model_name
            or os.getenv("GROQ_MODEL")
            or "openai/gpt-oss-20b"
        )

        if client is not None:
            self.client = client
            return

        resolved_api_key = (
            api_key
            or os.getenv("GROQ_API_KEY")
        )

        if not resolved_api_key:
            raise ValueError(
                "GROQ_API_KEY is required when using "
                "GroqAnalyzer."
            )

        self.client = Groq(
            api_key=resolved_api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    def analyze(
        self,
        candidate: AICandidateContext,
    ) -> AIReconciliationDecision:
        """
        Analyse one uncertain reconciliation candidate.

        Groq returns a strict JSON-schema response, which is then
        validated again using the application's Pydantic model.
        """

        candidate_json = candidate.model_dump_json(
            indent=2,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_INSTRUCTIONS,
                    },
                    {
                        "role": "user",
                        "content": (
                            "Review the following deterministic "
                            "reconciliation candidate and return only "
                            "the required structured decision.\n\n"
                            f"{candidate_json}"
                        ),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": (
                            "ai_reconciliation_decision"
                        ),
                        "strict": True,
                        "schema": GROQ_DECISION_SCHEMA,
                    },
                },
                temperature=0,
            )

        except APIError as error:
            status_code = getattr(
                error,
                "status_code",
                "unknown",
            )

            request_id = getattr(
                error,
                "request_id",
                "unavailable",
            )

            raise GroqAnalysisError(
                "The Groq reconciliation analysis failed. "
                f"Provider status: {status_code}. "
                f"Provider message: {error}. "
                f"Request ID: {request_id}."
            ) from error

        choices = getattr(
            response,
            "choices",
            None,
        )

        if not choices:
            raise GroqAnalysisError(
                "Groq returned no completion choices."
            )

        message = getattr(
            choices[0],
            "message",
            None,
        )

        content = getattr(
            message,
            "content",
            None,
        )

        if content is None or not str(content).strip():
            raise GroqAnalysisError(
                "Groq returned an empty reconciliation decision."
            )

        try:
            raw_decision = json.loads(
                str(content)
            )

            return AIReconciliationDecision.model_validate(
                raw_decision
            )

        except (
            json.JSONDecodeError,
            ValidationError,
        ) as error:
            raise GroqAnalysisError(
                "Groq returned an invalid reconciliation decision."
            ) from error