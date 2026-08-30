from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import ActionType, UseCase


class InteractionContext(BaseModel):
    """Everything the decision engine needs to know about *where* an AI
    response came from, beyond the risk signals themselves. Only the fields
    that materially change a policy decision in this prototype are modeled;
    see docs/assumptions.md for the fields intentionally left out."""

    use_case: UseCase
    geography: str = "US"
    business_domain: str = "general"
    action_type: ActionType = ActionType.INFORMATIONAL
    reversibility: str = Field(
        default="reversible", description="reversible | irreversible"
    )
    financial_exposure_usd: float = 0.0
    user_role: str = "customer"
    conversation_id: Optional[str] = None
    agent_mode: bool = False
