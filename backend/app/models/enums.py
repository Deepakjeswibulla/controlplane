"""Shared enumerations. Kept centralized so policy YAML keys, detector output,
and decision logic all reference the same vocabulary."""

from enum import Enum


class UseCase(str, Enum):
    CUSTOMER_SUPPORT = "customer_support"
    INTERNAL_KNOWLEDGE = "internal_knowledge"
    DECISION_SUPPORT = "decision_support"


class RiskDimension(str, Enum):
    PERFORMANCE = "performance"  # groundedness / evidence quality
    PRIVACY = "privacy"
    SECURITY = "security"
    COST = "cost"


class SeverityLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConsequenceTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionAction(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    EDIT = "edit"
    REDACT = "redact"
    REROUTE = "reroute"
    REVIEW = "review"
    BLOCK = "block"


class FailMode(str, Enum):
    FAIL_OPEN = "fail_open"
    FAIL_CLOSED = "fail_closed"


class ReviewOutcome(str, Enum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    ESCALATE = "escalate"


class ActionType(str, Enum):
    """What the AI interaction is trying to accomplish. Used by the
    consequence model alongside reversibility/financial exposure."""

    INFORMATIONAL = "informational"
    ACCOUNT_MODIFICATION = "account_modification"
    FINANCIAL_DECISION = "financial_decision"
    AGENT_TOOL_ACTION = "agent_tool_action"
