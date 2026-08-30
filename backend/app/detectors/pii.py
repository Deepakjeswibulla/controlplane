import re

from app.models.domain import Signal
from app.models.enums import SeverityLevel

# Deterministic, regex-first: fast, explainable, no model call needed for the
# common enterprise PII categories. Not a substitute for a full NER/DLP
# pipeline in production — see docs/assumptions.md.
_PATTERNS: dict[str, tuple[re.Pattern, SeverityLevel]] = {
    "ssn": (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), SeverityLevel.CRITICAL),
    "credit_card": (
        re.compile(r"\b(?:\d[ -]?){13,16}\b"),
        SeverityLevel.CRITICAL,
    ),
    "email": (
        re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
        SeverityLevel.MEDIUM,
    ),
    "phone": (
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
        SeverityLevel.MEDIUM,
    ),
    "policy_id": (
        re.compile(r"\bPOL-\d{4,}\b", re.IGNORECASE),
        SeverityLevel.LOW,
    ),
}

_SEVERITY_WEIGHT = {
    SeverityLevel.NONE: 0.0,
    SeverityLevel.LOW: 0.2,
    SeverityLevel.MEDIUM: 0.5,
    SeverityLevel.HIGH: 0.8,
    SeverityLevel.CRITICAL: 1.0,
}


def _luhn_valid(candidate: str) -> bool:
    digits = [int(c) for c in candidate if c.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def detect_pii(text: str) -> list[Signal]:
    findings: list[Signal] = []
    for category, (pattern, severity) in _PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(0)
            if category == "credit_card" and not _luhn_valid(value):
                continue
            findings.append(
                Signal(
                    type="pii",
                    category=category,
                    severity=severity,
                    confidence=0.99 if category in ("ssn", "credit_card") else 0.9,
                    description=f"Detected {category.replace('_', ' ')} pattern",
                    location=f"{match.start()}:{match.end()}",
                    metadata={"masked_value": _mask(value, category)},
                )
            )
    return findings


def _mask(value: str, category: str) -> str:
    if category in ("ssn", "credit_card"):
        return "*" * (len(value) - 4) + value[-4:]
    if category == "email":
        name, _, domain = value.partition("@")
        return f"{name[0]}***@{domain}"
    return "*" * max(len(value) - 2, 0) + value[-2:]


def pii_score(findings: list[Signal]) -> float:
    if not findings:
        return 0.0
    return max(_SEVERITY_WEIGHT[f.severity] for f in findings)


def redact(text: str, findings: list[Signal]) -> tuple[str, list[dict]]:
    """Replace each detected span with a category-tagged placeholder.
    Operates on the same patterns so spans stay consistent with detection."""
    redactions = []
    redacted = text
    for category, (pattern, _severity) in _PATTERNS.items():
        def _sub(m: re.Match, category=category) -> str:
            original = m.group(0)
            if category == "credit_card" and not _luhn_valid(original):
                return original
            replacement = f"[REDACTED_{category.upper()}]"
            redactions.append(
                {
                    "category": category,
                    "original_excerpt": _mask(original, category),
                    "replacement": replacement,
                }
            )
            return replacement

        redacted = pattern.sub(_sub, redacted)
    return redacted, redactions
