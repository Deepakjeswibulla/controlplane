import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.context import InteractionContext
from app.models.enums import (
    ConsequenceTier,
    DecisionAction,
    ReviewOutcome,
    RiskDimension,
    SeverityLevel,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return uuid.uuid4().hex[:12]


class Signal(BaseModel):
    """One atomic finding from a single detector."""

    type: str
    category: str
    severity: SeverityLevel
    confidence: float = Field(ge=0.0, le=1.0)
    description: str
    location: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskSignal(BaseModel):
    """Aggregated risk for one dimension (performance/privacy/security/cost),
    keeping the individual raw signals visible for explainability."""

    dimension: RiskDimension
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    signals: list[Signal] = Field(default_factory=list)


class EvidenceRef(BaseModel):
    document_id: str
    title: str
    excerpt: str
    similarity: float = Field(ge=0.0, le=1.0)


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    is_repeat: bool = False


class CostEvent(BaseModel):
    model_tier: str
    input_tokens: int
    output_tokens: int
    model_calls: int
    tool_calls: int
    retries: int
    expected_cost_usd: float
    actual_cost_usd: float

    @property
    def deviation_pct(self) -> float:
        if self.expected_cost_usd <= 0:
            return 0.0
        return round(
            (self.actual_cost_usd - self.expected_cost_usd)
            / self.expected_cost_usd
            * 100,
            1,
        )


class Redaction(BaseModel):
    category: str
    original_excerpt: str
    replacement: str


class Decision(BaseModel):
    action: DecisionAction
    reason: str
    what_happened: str
    why: str
    why_this_action: str
    consequence: ConsequenceTier
    required_escalation: bool = False
    policy_id: str


class HumanReview(BaseModel):
    id: str = Field(default_factory=_id)
    interaction_id: str
    outcome: Optional[ReviewOutcome] = None
    reviewer: Optional[str] = None
    notes: Optional[str] = None
    controlplane_recommendation: DecisionAction
    disagreement: bool = False
    created_at: datetime = Field(default_factory=_now)
    resolved_at: Optional[datetime] = None


class Interaction(BaseModel):
    id: str = Field(default_factory=_id)
    created_at: datetime = Field(default_factory=_now)
    turn_number: int = 1
    context: InteractionContext
    user_input: str
    ai_output: str
    verifier_mode: str = "DETERMINISTIC"
    claims: list[dict[str, Any]] = Field(default_factory=list)
    redacted_output: Optional[str] = None
    risk: dict[str, RiskSignal] = Field(default_factory=dict)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    redactions: list[Redaction] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    cost_event: Optional[CostEvent] = None
    decision: Optional[Decision] = None
    latency_ms: Optional[float] = None
    human_review: Optional[HumanReview] = None


class Conversation(BaseModel):
    id: str = Field(default_factory=_id)
    use_case: str
    created_at: datetime = Field(default_factory=_now)
    interaction_ids: list[str] = Field(default_factory=list)
    cumulative_risk: float = 0.0
