import os
from typing import Any

from dotenv import load_dotenv
from openai import APIError, OpenAI

from backend.ai_service import (
    AICandidateContext,
    AIReconciliationDecision,
)


SYSTEM_INSTRUCTIONS = """
You are a financial reconciliation review assistant.

Your task is to assess one reconciliation candidate produced by a
deterministic matching engine.

Rules:

1. Use only the candidate information supplied by the application.
2. Never invent invoice, payment, transaction, customer, or reference IDs.
3. Never describe a recommendation as a final accounting decision.
4. Every recommendation must require human review.
5. Confidence must remain between 0 and 95.
6. Recommend suggest_match only when the available evidence strongly
   supports the proposed relationship.
7. Recommend reject_match when the supplied evidence contains a material
   contradiction such as a currency mismatch.
8. Recommend needs_more_information when evidence is incomplete,
   duplicated, conflicting, or insufficient.
9. Explain the most important supporting signals and conflicts clearly.
10. Keep the explanation concise, factual, and suitable for an audit trail.
""".strip()


class OpenAIAnalysisError(RuntimeError):
    """
    Raised when an OpenAI reconciliation analysis cannot be completed.
    """


class OpenAIAnalyzer:
    """
    Production AI analyser backed by the OpenAI Responses API.

    The analyser implements the same interface as MockAIAnalyzer, allowing
    the application to switch providers without changing reconciliation
    logic.
    """

    provider = "openai"

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
        Configure the OpenAI analyser.

        A client may be injected during automated testing so that tests
        never make external API requests.
        """

        load_dotenv()

        self.model_name = (
            model_name
            or os.getenv("OPENAI_MODEL")
            or "gpt-5-mini"
        )

        if client is not None:
            self.client = client
            return

        resolved_api_key = (
            api_key
            or os.getenv("OPENAI_API_KEY")
        )

        if not resolved_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when using "
                "OpenAIAnalyzer."
            )

        self.client = OpenAI(
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

        The response is constrained to AIReconciliationDecision and can
        never automatically confirm a financial match.
        """

        candidate_json = candidate.model_dump_json(
            indent=2,
        )

        try:
            response = self.client.responses.parse(
                model=self.model_name,
                input=[
                    {
                        "role": "system",
                        "content": SYSTEM_INSTRUCTIONS,
                    },
                    {
                        "role": "user",
                        "content": (
                            "Review the following deterministic "
                            "reconciliation candidate and return the "
                            "required structured decision.\n\n"
                            f"{candidate_json}"
                        ),
                    },
                ],
                text_format=AIReconciliationDecision,
                store=False,
            )
        except APIError as error:
            request_id = getattr(
                error,
                "request_id",
                None,
            )

            request_context = (
                f" Request ID: {request_id}."
                if request_id
                else ""
            )

            raise OpenAIAnalysisError(
                "The OpenAI reconciliation analysis failed."
                f"{request_context}"
            ) from error

        parsed_decision = response.output_parsed

        if parsed_decision is None:
            raise OpenAIAnalysisError(
                "The OpenAI response did not contain a parsed "
                "reconciliation decision."
            )

        return AIReconciliationDecision.model_validate(
            parsed_decision
        )