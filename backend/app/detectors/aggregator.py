from app.detectors import cost as cost_detector
from app.detectors import evidence as evidence_detector
from app.detectors import injection as injection_detector
from app.detectors import pii as pii_detector
from app.models.domain import CostEvent, EvidenceRef, RiskSignal, Signal, ToolCall
from app.models.enums import RiskDimension


def run_detectors(
    *,
    user_input: str,
    ai_output: str,
    domain: str,
    tool_calls: list[ToolCall] | None = None,
    model_tier: str = "small",
    input_tokens: int = 200,
    output_tokens: int = 150,
    model_calls: int = 1,
    retries: int = 0,
    request_complexity: str = "simple",
) -> tuple[dict[str, RiskSignal], list[EvidenceRef], list[Signal], CostEvent]:
    """Runs all detectors and returns the risk vector, evidence refs, raw
    PII findings (needed for redaction), and the computed cost event.
    All detectors here are deterministic/regex/retrieval based, so running
    them sequentially is cheap; no async or parallel execution is needed for
    this scale of computation (see docs/assumptions.md)."""

    tool_calls = tool_calls or []

    pii_findings = pii_detector.detect_pii(user_input) + pii_detector.detect_pii(ai_output)
    injection_findings = injection_detector.detect_injection(user_input)

    verdict, evidence_signals, evidence_refs = evidence_detector.check_groundedness(
        ai_output, domain
    )

    cost_event = cost_detector.compute_cost_event(
        model_tier=model_tier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_calls=model_calls,
        tool_calls=tool_calls,
        retries=retries,
        request_complexity=request_complexity,
    )
    cost_findings = cost_detector.detect_cost_anomaly(cost_event, tool_calls, request_complexity)

    risk = {
        RiskDimension.PRIVACY.value: RiskSignal(
            dimension=RiskDimension.PRIVACY,
            score=pii_detector.pii_score(pii_findings),
            confidence=0.95 if pii_findings else 0.9,
            signals=pii_findings,
        ),
        RiskDimension.SECURITY.value: RiskSignal(
            dimension=RiskDimension.SECURITY,
            score=injection_detector.injection_score(injection_findings),
            confidence=0.8,
            signals=injection_findings,
        ),
        RiskDimension.PERFORMANCE.value: RiskSignal(
            dimension=RiskDimension.PERFORMANCE,
            score=evidence_detector.evidence_score(verdict),
            confidence=0.7,
            signals=evidence_signals,
        ),
        RiskDimension.COST.value: RiskSignal(
            dimension=RiskDimension.COST,
            score=cost_detector.cost_score(cost_findings),
            confidence=0.9 if cost_findings else 0.95,
            signals=cost_findings,
        ),
    }
    return risk, evidence_refs, pii_findings, cost_event
