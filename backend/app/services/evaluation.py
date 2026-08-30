import time

from app.decision.engine import decide
from app.detectors.aggregator import run_detectors
from app.detectors.pii import redact
from app.models.context import InteractionContext
from app.models.domain import Conversation, Interaction, Redaction, ToolCall
from app.models.enums import ActionType, DecisionAction
from app.services.storage import Storage

# Turns with performance risk >= this score count as "unresolved uncertainty"
# for the compounding-risk rule below.
_UNCERTAINTY_THRESHOLD = 0.6
_HIGH_IMPACT_ACTIONS = {ActionType.FINANCIAL_DECISION, ActionType.AGENT_TOOL_ACTION}


def evaluate_interaction(
    storage: Storage,
    *,
    user_input: str,
    ai_output: str,
    context: InteractionContext,
    tool_calls: list[ToolCall] | None = None,
    model_tier: str = "small",
    input_tokens: int = 200,
    output_tokens: int = 150,
    model_calls: int = 1,
    retries: int = 0,
    request_complexity: str = "simple",
    semantic_verification: dict | None = None,
) -> Interaction:
    start = time.perf_counter()

    risk, evidence, pii_findings, cost_event = run_detectors(
        user_input=user_input,
        ai_output=ai_output,
        domain=context.use_case.value,
        tool_calls=tool_calls,
        model_tier=model_tier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_calls=model_calls,
        retries=retries,
        request_complexity=request_complexity,
    )

    verifier_mode = "DETERMINISTIC"
    claims: list[dict] = []
    if semantic_verification is not None:
        verifier_mode = str(semantic_verification.get("provider_mode", "DETERMINISTIC"))
        claims = list(semantic_verification.get("claims", []))
        claim_verdicts = {str(c.get("verdict", "")).upper() for c in claims}
        if claim_verdicts & {"CONTRADICTED", "UNSUPPORTED"}:
            risk["performance"].score = max(risk["performance"].score, 0.9)
            risk["performance"].confidence = max(
                risk["performance"].confidence,
                max((float(c.get("confidence", 0.0)) for c in claims if str(c.get("verdict", "")).upper() in {"CONTRADICTED", "UNSUPPORTED"}), default=0.0),
            )
            from app.models.domain import Signal
            risk["performance"].signals.append(Signal(
                type="semantic_verification",
                category="claim_support",
                severity=__import__('app.models.enums', fromlist=['SeverityLevel']).SeverityLevel.HIGH,
                confidence=risk["performance"].confidence,
                description="Semantic verifier found an unsupported or contradicted claim in trusted evidence.",
                metadata={"overall_verdict": semantic_verification.get("overall_verdict", "")},
            ))
        elif "AMBIGUOUS" in claim_verdicts or "PARTIALLY_SUPPORTED" in claim_verdicts:
            risk["performance"].score = max(risk["performance"].score, 0.55)
            risk["performance"].confidence = max(risk["performance"].confidence, 0.65)

    decision = decide(risk, context)

    conversation, turn_number, prior_uncertainty = _load_conversation_state(storage, context)
    if prior_uncertainty and context.action_type in _HIGH_IMPACT_ACTIONS and decision.action != DecisionAction.BLOCK:
        decision.action = DecisionAction.REVIEW
        decision.required_escalation = True
        decision.reason = (
            "Escalated to REVIEW: a prior turn in this conversation left evidence "
            "unresolved, and this turn attempts a high-impact action."
        )
        decision.what_happened = "High-impact action requested after unresolved uncertainty earlier in the conversation."
        decision.why = "Compounding-risk rule: unresolved evidence gaps must not silently carry into consequential actions."
        decision.why_this_action = "Multi-turn context overrides the single-turn policy outcome for safety."

    redactions: list[Redaction] = []
    redacted_output = None
    if decision.action == DecisionAction.REDACT and pii_findings:
        redacted_text, raw_redactions = redact(ai_output, pii_findings)
        redacted_output = redacted_text
        redactions = [Redaction(**r) for r in raw_redactions]

    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    interaction = Interaction(
        turn_number=turn_number,
        context=context,
        user_input=user_input,
        ai_output=ai_output,
        redacted_output=redacted_output,
        risk=risk,
        evidence=evidence,
        redactions=redactions,
        tool_calls=tool_calls or [],
        cost_event=cost_event,
        decision=decision,
        latency_ms=latency_ms,
        verifier_mode=verifier_mode,
        claims=claims,
    )

    storage.save_interaction(interaction)
    _update_conversation(storage, conversation, interaction, risk)
    return interaction


def _load_conversation_state(
    storage: Storage, context: InteractionContext
) -> tuple[Conversation | None, int, bool]:
    if not context.conversation_id:
        return None, 1, False

    conversation = storage.get_conversation(context.conversation_id)
    if conversation is None:
        conversation = Conversation(id=context.conversation_id, use_case=context.use_case.value)
        return conversation, 1, False

    prior_uncertainty = False
    for interaction_id in conversation.interaction_ids:
        prior = storage.get_interaction(interaction_id)
        if prior and prior.risk.get("performance") and prior.risk["performance"].score >= _UNCERTAINTY_THRESHOLD:
            prior_uncertainty = True
            break

    turn_number = len(conversation.interaction_ids) + 1
    return conversation, turn_number, prior_uncertainty


def _update_conversation(storage, conversation, interaction, risk) -> None:
    if conversation is None:
        return
    conversation.interaction_ids.append(interaction.id)
    max_score = max((r.score for r in risk.values()), default=0.0)
    n = len(conversation.interaction_ids)
    conversation.cumulative_risk = round(
        (conversation.cumulative_risk * (n - 1) + max_score) / n, 3
    )
    storage.save_conversation(conversation)
