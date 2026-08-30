import logging

from app.decision.consequence import compute_consequence
from app.decision.severity import score_to_level
from app.models.context import InteractionContext
from app.models.domain import Decision, RiskSignal
from app.models.enums import ConsequenceTier, DecisionAction, FailMode
from app.models.policy import Policy
from app.policy.loader import PolicyLoadError, get_policy

logger = logging.getLogger("controlplane.decision")

# Explicit ordering so that when multiple policy rules fire, the engine
# applies the most restrictive one rather than the first/last one evaluated.
_ACTION_RANK = [
    DecisionAction.ALLOW,
    DecisionAction.WARN,
    DecisionAction.EDIT,
    DecisionAction.REDACT,
    DecisionAction.REROUTE,
    DecisionAction.REVIEW,
    DecisionAction.BLOCK,
]


def _more_restrictive(a: DecisionAction, b: DecisionAction) -> DecisionAction:
    return a if _ACTION_RANK.index(a) >= _ACTION_RANK.index(b) else b


def decide(
    risk: dict[str, RiskSignal], context: InteractionContext
) -> Decision:
    try:
        policy = get_policy(context.use_case.value)
    except PolicyLoadError as exc:
        logger.error("Policy load failed, applying failsafe: %s", exc)
        return _failsafe_decision(str(exc))

    consequence, consequence_index = compute_consequence(risk, context)

    triggered: list[tuple[str, str, DecisionAction]] = []
    action = DecisionAction.ALLOW
    for dimension, signal in risk.items():
        level = score_to_level(signal.score)
        dim_action = policy.action_for(dimension, level)
        if dim_action is not None:
            triggered.append((dimension, level, dim_action))
            action = _more_restrictive(action, dim_action)

    consequence_action = policy.action_for_consequence(consequence)
    if consequence_action is not None:
        action = _more_restrictive(action, consequence_action)

    return _build_decision(action, triggered, consequence, policy, context)


def _build_decision(
    action: DecisionAction,
    triggered: list[tuple[str, str, DecisionAction]],
    consequence: ConsequenceTier,
    policy: Policy,
    context: InteractionContext,
) -> Decision:
    if action == DecisionAction.ALLOW:
        return Decision(
            action=action,
            reason="No policy threshold exceeded for the observed risk signals.",
            what_happened="All detectors returned low or no risk.",
            why="Risk scores stayed below every configured threshold for this use case.",
            why_this_action=f"'{policy.use_case}' policy allows interactions with no elevated risk.",
            consequence=consequence,
            required_escalation=False,
            policy_id=policy.policy_id,
        )

    driving = [t for t in triggered if t[2] == action]
    dims = ", ".join(sorted({d for d, _lvl, _a in driving})) or "consequence"
    levels = ", ".join(sorted({lvl for _d, lvl, _a in driving})) or consequence.value

    return Decision(
        action=action,
        reason=f"{dims} risk reached '{levels}', requiring '{action.value}' under this policy.",
        what_happened=f"Detectors flagged elevated risk in: {dims}.",
        why=f"Observed severity level(s) [{levels}] for {dims} exceed the configured threshold.",
        why_this_action=(
            f"Policy '{policy.policy_id}' maps this risk/consequence combination "
            f"(consequence={consequence.value}) to action '{action.value}'."
        ),
        consequence=consequence,
        required_escalation=action in (DecisionAction.REVIEW, DecisionAction.BLOCK),
        policy_id=policy.policy_id,
    )


def _failsafe_decision(error: str) -> Decision:
    """ControlPlane itself failed (bad policy, missing config, etc). The
    action taken depends on fail_mode; without a loaded policy we cannot
    read fail_mode, so we default to the safer FAIL_CLOSED behavior."""
    fail_mode = FailMode.FAIL_CLOSED
    action = DecisionAction.BLOCK if fail_mode == FailMode.FAIL_CLOSED else DecisionAction.ALLOW
    return Decision(
        action=action,
        reason=f"ControlPlane failure: {error}",
        what_happened="ControlPlane could not evaluate policy for this interaction.",
        why="An internal error occurred while loading or applying policy.",
        why_this_action=f"Default failsafe mode '{fail_mode.value}' was applied.",
        consequence=ConsequenceTier.HIGH,
        required_escalation=True,
        policy_id="failsafe",
    )
