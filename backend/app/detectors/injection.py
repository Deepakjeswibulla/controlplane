import re

from app.models.domain import Signal
from app.models.enums import SeverityLevel

# Demonstration-grade rule set, not a production adversarial-robust
# classifier. Patterns are grouped by intent category so the dashboard can
# explain *why* something was flagged rather than showing a bare score.
_RULES: list[tuple[str, re.Pattern, SeverityLevel]] = [
    (
        "instruction_override",
        re.compile(r"ignore (all|any|the)?\s*(previous|prior|above) instructions", re.I),
        SeverityLevel.HIGH,
    ),
    (
        "system_prompt_exfiltration",
        re.compile(r"(reveal|show|print|repeat) (your |the )?system prompt", re.I),
        SeverityLevel.HIGH,
    ),
    (
        "policy_bypass",
        re.compile(r"(bypass|disable|turn off|ignore).{0,20}(policy|safety|guardrail|filter)", re.I),
        SeverityLevel.HIGH,
    ),
    (
        "secret_exfiltration",
        re.compile(r"(api key|credential|password|secret token).{0,20}(is|are|:)", re.I),
        SeverityLevel.MEDIUM,
    ),
    (
        "unauthorized_tool_use",
        re.compile(r"(delete|drop|wire|transfer).{0,20}(database|table|funds|money).{0,20}(without|no) (approval|confirmation)", re.I),
        SeverityLevel.CRITICAL,
    ),
    (
        "role_override",
        re.compile(r"you are now (in )?(developer|admin|unrestricted|dan) mode", re.I),
        SeverityLevel.MEDIUM,
    ),
]


def detect_injection(text: str) -> list[Signal]:
    findings: list[Signal] = []
    for category, pattern, severity in _RULES:
        match = pattern.search(text)
        if match:
            findings.append(
                Signal(
                    type="injection",
                    category=category,
                    severity=severity,
                    confidence=0.75,
                    description=f"Matched '{category}' pattern in request text",
                    location=f"{match.start()}:{match.end()}",
                )
            )
    return findings


_WEIGHT = {
    SeverityLevel.NONE: 0.0,
    SeverityLevel.LOW: 0.2,
    SeverityLevel.MEDIUM: 0.55,
    SeverityLevel.HIGH: 0.8,
    SeverityLevel.CRITICAL: 1.0,
}


def injection_score(findings: list[Signal]) -> float:
    if not findings:
        return 0.0
    return max(_WEIGHT[f.severity] for f in findings)
