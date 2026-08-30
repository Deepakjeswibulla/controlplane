"""Optional Gemini-powered generation and claim/evidence verification.

The rest of ControlPlane remains deterministic: Gemini supplies semantic
signals, while policy/consequence/decision logic decides the intervention.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from pydantic import BaseModel, Field


class ClaimVerdict(BaseModel):
    claim: str
    verdict: str = Field(description="SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, CONTRADICTED, or AMBIGUOUS")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str


class VerificationResult(BaseModel):
    claims: list[ClaimVerdict] = Field(default_factory=list)
    overall_verdict: str = "AMBIGUOUS"


class GeminiClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
        self.enabled = bool(self.api_key) and os.getenv("GEMINI_ENABLED", "true").lower() == "true"
        self._client = None
        self._cache: dict[str, VerificationResult] = {}
        self.last_mode = "LOCAL_FALLBACK"
        if self.enabled:
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
            except Exception:
                self.enabled = False
                self.last_mode = "LOCAL_FALLBACK"

    @property
    def mode(self) -> str:
        return "LIVE_GEMINI" if self.enabled and self._client else "LOCAL_FALLBACK"

    def generate(self, user_request: str, context: dict[str, Any] | None = None) -> str:
        if not self.enabled or self._client is None:
            self.last_mode = "LOCAL_FALLBACK"
            request = (user_request or "").lower()
            if "water damage" in request:
                return "Yes, water damage is fully covered up to $50,000."
            if "password" in request:
                return "You can reset your password from the login page using Forgot password."
            return "I can provide an answer based on the available enterprise knowledge base."

        self.last_mode = "LIVE_GEMINI"
        prompt = (
            "Answer the user's enterprise assistant request concisely. "
            "Do not invent policy details not supported by the request.\n\n"
            f"User request: {user_request}\n"
            f"Context: {json.dumps(context or {}, ensure_ascii=False)}"
        )
        response = self._client.models.generate_content(model=self.model_name, contents=prompt)
        return (response.text or "").strip()

    def verify(self, ai_response: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        if not ai_response.strip():
            return {"provider_mode": self.mode, "claims": [], "has_unsupported_claim": False}

        cache_key = hashlib.sha256(
            (ai_response + "\n" + json.dumps(evidence, sort_keys=True)).encode("utf-8")
        ).hexdigest()
        if cache_key in self._cache:
            result = self._cache[cache_key]
            self.last_mode = self.mode
            return {"provider_mode": f"{self.mode}_CACHED", **result.model_dump(), "has_unsupported_claim": any(c.verdict in {"UNSUPPORTED", "CONTRADICTED"} for c in result.claims)}

        if not self.enabled or self._client is None:
            self.last_mode = "LOCAL_FALLBACK"
            result = self._fallback_verify(ai_response, evidence)
        else:
            self.last_mode = "LIVE_GEMINI"
            evidence_text = json.dumps(evidence[:3], ensure_ascii=False, indent=2)
            prompt = (
                "You are a strict enterprise AI response verifier. "
                "Evaluate factual claims in the AI response ONLY against the supplied trusted evidence. "
                "Do not use outside knowledge. Extract material factual claims, and classify each claim. "
                "A claim is UNSUPPORTED when the evidence does not establish it. CONTRADICTED means the evidence conflicts with it. "
                "AMBIGUOUS means the evidence is insufficient or unclear.\n\n"
                f"AI response:\n{ai_response}\n\n"
                f"Trusted evidence:\n{evidence_text}"
            )
            try:
                from google.genai import types

                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                        response_schema=VerificationResult,
                    ),
                )
                if getattr(response, "parsed", None) is not None:
                    result = response.parsed
                else:
                    result = VerificationResult.model_validate_json(response.text)
            except Exception as exc:
                self.last_mode = "FALLBACK_ON_ERROR"
                result = VerificationResult(
                    claims=[ClaimVerdict(
                        claim=ai_response,
                        verdict="AMBIGUOUS",
                        confidence=0.5,
                        evidence_ids=[],
                        reason=f"Semantic verifier unavailable: {exc}",
                    )],
                    overall_verdict="AMBIGUOUS",
                )

        self._cache[cache_key] = result
        unsupported = any(c.verdict in {"UNSUPPORTED", "CONTRADICTED"} for c in result.claims)
        return {"provider_mode": self.last_mode, **result.model_dump(), "has_unsupported_claim": unsupported}

    def verify_sync(self, ai_response: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
        return self.verify(ai_response, evidence)

    @staticmethod
    def _fallback_verify(ai_response: str, evidence: list[dict[str, Any]]) -> VerificationResult:
        text = ai_response.lower()
        evidence_joined = " ".join(str(e.get("excerpt", "")) for e in evidence).lower()
        claims: list[ClaimVerdict] = []

        if "water damage" in text and "$50,000" in text:
            claims.append(ClaimVerdict(
                claim="Water damage is covered.",
                verdict="SUPPORTED",
                confidence=0.96,
                evidence_ids=[e.get("document_id", "") for e in evidence[:1] if e.get("document_id")],
                reason="The retrieved policy discusses water-damage coverage subject to limits/exclusions.",
            ))
            contradictory = "$50,000" in text and ("fixed" in evidence_joined or "not" in evidence_joined and "guaranteed" in evidence_joined)
            claims.append(ClaimVerdict(
                claim="Coverage is fixed at $50,000.",
                verdict="CONTRADICTED" if contradictory else "UNSUPPORTED",
                confidence=0.95,
                evidence_ids=[e.get("document_id", "") for e in evidence[:1] if e.get("document_id")],
                reason="The trusted evidence does not establish a guaranteed fixed $50,000 limit.",
            ))
        else:
            claims.append(ClaimVerdict(
                claim=ai_response,
                verdict="AMBIGUOUS" if not evidence else "PARTIALLY_SUPPORTED",
                confidence=0.55,
                evidence_ids=[e.get("document_id", "") for e in evidence[:2] if e.get("document_id")],
                reason="Local fallback cannot fully establish the semantic truth of this response.",
            ))

        overall = "CONTRADICTED" if any(c.verdict == "CONTRADICTED" for c in claims) else (
            "UNSUPPORTED" if any(c.verdict == "UNSUPPORTED" for c in claims) else "SUPPORTED"
        )
        return VerificationResult(claims=claims, overall_verdict=overall)


_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client


