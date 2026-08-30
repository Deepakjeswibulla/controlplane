from app.models.context import InteractionContext
from app.models.domain import RiskSignal
from app.models.enums import ConsequenceTier

# Engineering heuristic for the prototype, not a validated risk model
# (see docs/assumptions.md). consequence_index blends the worst observed
# risk severity with context signals about how much a mistake would matter.


def _max_risk_score(risk: dict[str, RiskSignal]) -> float:
    return max((r.score for r in risk.values()), default=0.0)


def _reversibility_weight(context: InteractionContext) -> float:
    return 1.0 if context.reversibility == "irreversible" else 0.5


def _financial_weight(context: InteractionContext) -> float:
    exposure = context.financial_exposure_usd
    if exposure <= 0:
        return 0.1
    if exposure < 1_000:
        return 0.3
    if exposure < 25_000:
        return 0.6
    return 1.0


def compute_consequence(
    risk: dict[str, RiskSignal], context: InteractionContext
) -> tuple[ConsequenceTier, float]:
    severity = _max_risk_score(risk)
    exposure_weight = _financial_weight(context)
    reversibility_weight = _reversibility_weight(context)

    index = severity * 0.5 + exposure_weight * 0.3 + reversibility_weight * 0.2

    if index >= 0.75:
        tier = ConsequenceTier.CRITICAL
    elif index >= 0.5:
        tier = ConsequenceTier.HIGH
    elif index >= 0.25:
        tier = ConsequenceTier.MEDIUM
    else:
        tier = ConsequenceTier.LOW

    return tier, round(index, 3)
