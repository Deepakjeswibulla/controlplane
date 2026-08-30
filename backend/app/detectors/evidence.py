import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.models.domain import EvidenceRef, Signal
from app.models.enums import SeverityLevel

_KB_PATH = Path(__file__).resolve().parents[3] / "data" / "knowledge" / "kb.json"

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "for", "of", "to", "and",
    "in", "on", "does", "do", "this", "that", "it", "your", "my", "will",
    "can", "with", "as", "by", "be", "has", "have", "not",
}

# Negation / exclusion cues let the checker tell "policy covers X" apart from
# "policy does not cover X" without a full NLI model — deterministic and
# transparent, at the cost of missing subtler contradictions.
_NEGATION_CUES = ("does not", "doesn't", "excludes", "excluded", "not cover", "no coverage")


@dataclass
class RetrievedChunk:
    doc_id: str
    title: str
    text: str
    similarity: float


@lru_cache(maxsize=1)
def _load_kb() -> list[dict]:
    with open(_KB_PATH, encoding="utf-8") as f:
        return json.load(f)


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def retrieve(claim: str, domain: str, top_k: int = 3) -> list[RetrievedChunk]:
    claim_tokens = _tokenize(claim)
    candidates = [d for d in _load_kb() if d["domain"] == domain] or _load_kb()
    scored = []
    for doc in candidates:
        sim = _jaccard(claim_tokens, _tokenize(doc["text"]))
        scored.append(RetrievedChunk(doc["id"], doc["title"], doc["text"], sim))
    scored.sort(key=lambda c: c.similarity, reverse=True)
    return scored[:top_k]


def check_groundedness(
    claim: str, domain: str
) -> tuple[str, list[Signal], list[EvidenceRef]]:
    """Returns (verdict, signals, evidence). Verdict in
    {SUPPORTED, WEAKLY_SUPPORTED, UNSUPPORTED, CONTRADICTED}."""
    chunks = retrieve(claim, domain)
    evidence = [
        EvidenceRef(document_id=c.doc_id, title=c.title, excerpt=c.text, similarity=round(c.similarity, 3))
        for c in chunks
        if c.similarity > 0
    ]

    top = chunks[0] if chunks else None
    claim_asserts_coverage = bool(
        re.search(r"\b(cover|covers|covered|included|eligible)\b", claim, re.I)
    ) and not any(cue in claim.lower() for cue in _NEGATION_CUES)

    if top is None or top.similarity == 0.0:
        verdict = "UNSUPPORTED"
        severity = SeverityLevel.HIGH
        desc = "No supporting document found in the knowledge base for this claim."
    elif claim_asserts_coverage and any(cue in top.text.lower() for cue in _NEGATION_CUES):
        verdict = "CONTRADICTED"
        severity = SeverityLevel.CRITICAL
        desc = f"Claim conflicts with '{top.title}', which explicitly excludes this."
    elif top.similarity >= 0.22:
        verdict = "SUPPORTED"
        severity = SeverityLevel.NONE
        desc = f"Claim is supported by '{top.title}' (similarity {top.similarity:.2f})."
    elif top.similarity >= 0.10:
        verdict = "WEAKLY_SUPPORTED"
        severity = SeverityLevel.MEDIUM
        desc = f"Only partial overlap with '{top.title}' (similarity {top.similarity:.2f}); evidence is thin."
    else:
        verdict = "UNSUPPORTED"
        severity = SeverityLevel.HIGH
        desc = "Retrieved documents do not sufficiently support this claim."

    signal = Signal(
        type="evidence",
        category=verdict.lower(),
        severity=severity,
        confidence=0.7,
        description=desc,
        metadata={"top_similarity": round(top.similarity, 3) if top else 0.0},
    )
    return verdict, [signal], evidence


_VERDICT_WEIGHT = {
    "SUPPORTED": 0.0,
    "WEAKLY_SUPPORTED": 0.5,
    "UNSUPPORTED": 0.75,
    "CONTRADICTED": 1.0,
}


def evidence_score(verdict: str) -> float:
    return _VERDICT_WEIGHT.get(verdict, 0.5)
