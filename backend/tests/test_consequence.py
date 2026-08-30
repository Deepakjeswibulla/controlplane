from app.decision.consequence import compute_consequence
from app.models.context import InteractionContext
from app.models.domain import RiskSignal
from app.models.enums import ConsequenceTier, RiskDimension, UseCase


def _risk(score: float) -> dict:
    return {
        "performance": RiskSignal(dimension=RiskDimension.PERFORMANCE, score=score, confidence=0.8, signals=[])
    }


def test_low_risk_low_exposure_is_low_consequence():
    ctx = InteractionContext(use_case=UseCase.CUSTOMER_SUPPORT, financial_exposure_usd=0)
    tier, index = compute_consequence(_risk(0.1), ctx)
    assert tier == ConsequenceTier.LOW


def test_high_risk_high_exposure_irreversible_is_critical():
    ctx = InteractionContext(
        use_case=UseCase.DECISION_SUPPORT,
        financial_exposure_usd=50000,
        reversibility="irreversible",
    )
    tier, index = compute_consequence(_risk(1.0), ctx)
    assert tier == ConsequenceTier.CRITICAL


def test_consequence_increases_monotonically_with_risk():
    ctx = InteractionContext(use_case=UseCase.CUSTOMER_SUPPORT, financial_exposure_usd=100)
    _, low_index = compute_consequence(_risk(0.1), ctx)
    _, high_index = compute_consequence(_risk(0.9), ctx)
    assert high_index > low_index
