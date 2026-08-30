from app.decision.engine import decide
from app.models.context import InteractionContext
from app.models.domain import RiskSignal
from app.models.enums import ActionType, DecisionAction, RiskDimension, UseCase


def _risk(performance=0.0, privacy=0.0, security=0.0, cost=0.0) -> dict:
    return {
        "performance": RiskSignal(dimension=RiskDimension.PERFORMANCE, score=performance, confidence=0.8, signals=[]),
        "privacy": RiskSignal(dimension=RiskDimension.PRIVACY, score=privacy, confidence=0.8, signals=[]),
        "security": RiskSignal(dimension=RiskDimension.SECURITY, score=security, confidence=0.8, signals=[]),
        "cost": RiskSignal(dimension=RiskDimension.COST, score=cost, confidence=0.8, signals=[]),
    }


def test_no_risk_allows():
    ctx = InteractionContext(use_case=UseCase.CUSTOMER_SUPPORT)
    decision = decide(_risk(), ctx)
    assert decision.action == DecisionAction.ALLOW


def test_critical_privacy_redacts_in_customer_support():
    ctx = InteractionContext(use_case=UseCase.CUSTOMER_SUPPORT)
    decision = decide(_risk(privacy=0.95), ctx)
    assert decision.action == DecisionAction.REDACT


def test_security_risk_blocks_regardless_of_use_case():
    for uc in (UseCase.CUSTOMER_SUPPORT, UseCase.INTERNAL_KNOWLEDGE, UseCase.DECISION_SUPPORT):
        ctx = InteractionContext(use_case=uc)
        decision = decide(_risk(security=0.9), ctx)
        assert decision.action == DecisionAction.BLOCK


def test_same_performance_risk_different_action_by_use_case():
    """The central product claim: identical risk signal, different context
    -> different action."""
    risk = _risk(performance=0.65)  # 'high' bucket

    support_decision = decide(risk, InteractionContext(use_case=UseCase.CUSTOMER_SUPPORT))
    knowledge_decision = decide(risk, InteractionContext(use_case=UseCase.INTERNAL_KNOWLEDGE))
    decision_support_decision = decide(
        risk,
        InteractionContext(
            use_case=UseCase.DECISION_SUPPORT,
            action_type=ActionType.FINANCIAL_DECISION,
            financial_exposure_usd=20000,
        ),
    )

    assert support_decision.action == DecisionAction.WARN
    assert knowledge_decision.action == DecisionAction.REVIEW
    assert decision_support_decision.action in (DecisionAction.REVIEW, DecisionAction.BLOCK)

    # Prove the three actions aren't all identical, i.e. context mattered.
    actions = {support_decision.action, knowledge_decision.action, decision_support_decision.action}
    assert len(actions) >= 2


def test_decision_explanation_fields_present_on_non_allow():
    ctx = InteractionContext(use_case=UseCase.CUSTOMER_SUPPORT)
    decision = decide(_risk(privacy=0.95), ctx)
    assert decision.what_happened
    assert decision.why
    assert decision.why_this_action
    assert decision.reason
