from app.models.domain import CostEvent, Signal, ToolCall
from app.models.enums import SeverityLevel

# Simulated per-1K-token pricing by model tier. These are illustrative
# constants for the prototype, not real provider billing rates.
_PRICE_PER_1K = {
    "small": {"input": 0.0005, "output": 0.0015},
    "medium": {"input": 0.003, "output": 0.015},
    "large": {"input": 0.01, "output": 0.03},
}

_EXPECTED_TOOL_CALLS_BY_COMPLEXITY = {
    "simple": 1,
    "moderate": 3,
    "complex": 6,
}


def compute_cost_event(
    model_tier: str,
    input_tokens: int,
    output_tokens: int,
    model_calls: int,
    tool_calls: list[ToolCall],
    retries: int,
    request_complexity: str = "simple",
) -> CostEvent:
    price = _PRICE_PER_1K.get(model_tier, _PRICE_PER_1K["small"])
    actual_cost = (
        (input_tokens / 1000) * price["input"]
        + (output_tokens / 1000) * price["output"]
    ) * max(model_calls, 1)

    expected_tier = "small" if request_complexity == "simple" else model_tier
    expected_price = _PRICE_PER_1K.get(expected_tier, price)
    expected_calls = _EXPECTED_TOOL_CALLS_BY_COMPLEXITY.get(request_complexity, 2)
    expected_cost = (
        (input_tokens / 1000) * expected_price["input"]
        + (output_tokens / 1000) * expected_price["output"]
    ) * 1  # a well-behaved request needs exactly one model call

    return CostEvent(
        model_tier=model_tier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_calls=model_calls,
        tool_calls=len(tool_calls),
        retries=retries,
        expected_cost_usd=round(max(expected_cost, 0.0001), 6),
        actual_cost_usd=round(max(actual_cost, 0.0001), 6),
    )


def detect_cost_anomaly(
    cost_event: CostEvent,
    tool_calls: list[ToolCall],
    request_complexity: str = "simple",
) -> list[Signal]:
    findings: list[Signal] = []

    expected_calls = _EXPECTED_TOOL_CALLS_BY_COMPLEXITY.get(request_complexity, 2)
    if cost_event.tool_calls > expected_calls * 2 and cost_event.tool_calls >= 4:
        findings.append(
            Signal(
                type="cost",
                category="excessive_tool_calls",
                severity=SeverityLevel.HIGH,
                confidence=0.9,
                description=(
                    f"Expected ~{expected_calls} tool calls for a '{request_complexity}' "
                    f"request, observed {cost_event.tool_calls}."
                ),
                metadata={"expected": expected_calls, "actual": cost_event.tool_calls},
            )
        )

    repeats = sum(1 for t in tool_calls if t.is_repeat)
    if repeats >= 2:
        findings.append(
            Signal(
                type="cost",
                category="repeated_identical_calls",
                severity=SeverityLevel.MEDIUM,
                confidence=0.85,
                description=f"Detected {repeats} repeated identical tool calls, suggesting a loop.",
                metadata={"repeat_count": repeats},
            )
        )

    if cost_event.deviation_pct >= 100:
        findings.append(
            Signal(
                type="cost",
                category="cost_deviation",
                severity=SeverityLevel.HIGH if cost_event.deviation_pct >= 200 else SeverityLevel.MEDIUM,
                confidence=0.95,
                description=f"Actual cost exceeded expected cost by {cost_event.deviation_pct}%.",
                metadata={
                    "expected_cost_usd": cost_event.expected_cost_usd,
                    "actual_cost_usd": cost_event.actual_cost_usd,
                },
            )
        )

    if request_complexity == "simple" and cost_event.model_tier == "large":
        findings.append(
            Signal(
                type="cost",
                category="model_overkill",
                severity=SeverityLevel.LOW,
                confidence=0.7,
                description="A large-tier model was used for a simple request.",
            )
        )

    if cost_event.retries >= 3:
        findings.append(
            Signal(
                type="cost",
                category="excessive_retries",
                severity=SeverityLevel.MEDIUM,
                confidence=0.8,
                description=f"{cost_event.retries} retries observed for a single interaction.",
            )
        )

    return findings


_WEIGHT = {
    SeverityLevel.NONE: 0.0,
    SeverityLevel.LOW: 0.15,
    SeverityLevel.MEDIUM: 0.45,
    SeverityLevel.HIGH: 0.75,
    SeverityLevel.CRITICAL: 1.0,
}


def cost_score(findings: list[Signal]) -> float:
    if not findings:
        return 0.0
    # Multiple compounding anomalies should read as riskier than one alone.
    base = max(_WEIGHT[f.severity] for f in findings)
    bonus = min(0.15 * (len(findings) - 1), 0.25)
    return min(base + bonus, 1.0)
