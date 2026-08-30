from typing import Optional

from pydantic import BaseModel, Field

from app.models.context import InteractionContext
from app.models.domain import Interaction, ToolCall
from app.models.enums import ReviewOutcome


class EvaluateRequest(BaseModel):
    user_input: str
    ai_output: str = ""
    generate_with_gemini: bool = False
    context: InteractionContext
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model_tier: str = "small"
    input_tokens: int = 200
    output_tokens: int = 150
    model_calls: int = 1
    retries: int = 0
    request_complexity: str = "simple"


class EvaluateResponse(BaseModel):
    interaction_id: str
    user_input: str = ""
    raw_ai_response: str = ""
    risk: dict[str, float] = Field(default_factory=dict)
    consequence: str
    decision: str
    reason: str
    evidence: list[dict]
    redactions: list[dict]
    redacted_output: Optional[str] = None
    latency_ms: Optional[float] = None
    verifier_mode: str = "DETERMINISTIC"
    claims: list[dict] = Field(default_factory=list)

    @classmethod
    def from_interaction(cls, interaction: Interaction) -> "EvaluateResponse":
        decision = interaction.decision
        return cls(
            interaction_id=interaction.id,
            user_input=interaction.user_input,
            raw_ai_response=interaction.ai_output,
            risk={dim: sig.score for dim, sig in interaction.risk.items()},
            consequence=decision.consequence.value if decision else "unknown",
            decision=decision.action.value if decision else "unknown",
            reason=decision.reason if decision else "",
            evidence=[e.model_dump() for e in interaction.evidence],
            redactions=[r.model_dump() for r in interaction.redactions],
            redacted_output=interaction.redacted_output,
            latency_ms=interaction.latency_ms,
            verifier_mode=interaction.verifier_mode,
            claims=interaction.claims,
        )


class ReviewRequest(BaseModel):
    outcome: ReviewOutcome
    reviewer: str = "demo_reviewer"
    notes: Optional[str] = None
