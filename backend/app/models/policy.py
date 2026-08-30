from pydantic import BaseModel, Field, field_validator

from app.models.enums import ConsequenceTier, DecisionAction, FailMode

_VALID_LEVELS = {"low", "medium", "high", "critical"}


class Policy(BaseModel):
    policy_id: str
    use_case: str
    fail_mode: FailMode = FailMode.FAIL_OPEN
    description: str = ""
    thresholds: dict[str, dict[str, DecisionAction]] = Field(default_factory=dict)
    consequence_overrides: dict[str, DecisionAction] = Field(default_factory=dict)

    @field_validator("thresholds")
    @classmethod
    def _validate_levels(cls, v):
        for dimension, levels in v.items():
            bad = set(levels) - _VALID_LEVELS
            if bad:
                raise ValueError(f"Invalid severity level(s) {bad} for dimension '{dimension}'")
        return v

    def action_for(self, dimension: str, level: str) -> DecisionAction | None:
        return self.thresholds.get(dimension, {}).get(level)

    def action_for_consequence(self, tier: ConsequenceTier) -> DecisionAction | None:
        return self.consequence_overrides.get(tier.value)
