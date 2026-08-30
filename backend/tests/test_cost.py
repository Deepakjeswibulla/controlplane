from app.detectors.cost import compute_cost_event, detect_cost_anomaly
from app.models.domain import ToolCall


def test_normal_usage_has_no_anomaly():
    tool_calls = [ToolCall(name="search_kb")]
    event = compute_cost_event(
        model_tier="small",
        input_tokens=200,
        output_tokens=100,
        model_calls=1,
        tool_calls=tool_calls,
        retries=0,
        request_complexity="simple",
    )
    findings = detect_cost_anomaly(event, tool_calls, "simple")
    assert findings == []


def test_excessive_tool_calls_detected():
    tool_calls = [ToolCall(name="search_kb", is_repeat=(i > 0)) for i in range(8)]
    event = compute_cost_event(
        model_tier="large",
        input_tokens=200,
        output_tokens=100,
        model_calls=8,
        tool_calls=tool_calls,
        retries=0,
        request_complexity="simple",
    )
    findings = detect_cost_anomaly(event, tool_calls, "simple")
    categories = {f.category for f in findings}
    assert "excessive_tool_calls" in categories
    assert "repeated_identical_calls" in categories
    assert event.deviation_pct > 0


def test_excessive_retries_detected():
    event = compute_cost_event(
        model_tier="small",
        input_tokens=100,
        output_tokens=50,
        model_calls=4,
        tool_calls=[],
        retries=3,
        request_complexity="simple",
    )
    findings = detect_cost_anomaly(event, [], "simple")
    assert any(f.category == "excessive_retries" for f in findings)
