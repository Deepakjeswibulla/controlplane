# ControlPlane.ai

> **A context-aware, policy-driven runtime control layer for enterprise AI.**

Round 2 competition prototype. This is a working proof-of-concept, not a
finished product — see [Known limitations](#known-limitations) and
[docs/assumptions.md](docs/assumptions.md) for exactly what is real versus
simulated.

---

## Problem

Enterprises are putting AI in front of customers, employees, and
high-stakes decisions. Most "AI safety" tooling treats every risky output
the same way — score it, maybe block it. But the same underlying risk (an
unsupported claim, a borderline answer) has wildly different consequences
depending on *where* it shows up: a shaky FAQ answer is a minor annoyance;
the same shaky reasoning behind an insurance claim approval is a real
liability.

## Solution

ControlPlane sits between an AI application and the business consequence
of its output. It runs lightweight, mostly deterministic risk detectors,
combines the findings with the interaction's context (use case, financial
exposure, reversibility, conversation history), checks the applicable
policy, and returns one clear action: **ALLOW, WARN, EDIT, REDACT,
REROUTE, REVIEW, or BLOCK** — with a full explanation.

## Core insight

> **A risk signal alone is not enough. ControlPlane interprets that signal
> in context and applies the appropriate policy before the AI output or
> action is allowed to proceed.**

The flagship demo proves this directly: the *identical* unsupported
insurance claim is sent through three different use-case policies and
receives three different actions — WARN, REVIEW, and BLOCK — because the
context and consequence differ, not because the detector output differs.

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full module-level
breakdown. In short:

```
Input --> [PII | Injection | Evidence | Cost detectors] --> Risk vector
       --> Consequence model + Policy engine --> Decision engine
       --> (redaction if needed) --> stored + explainable
```

Detection, context, policy, and decision are separate modules with no
circular dependencies — each is independently unit-tested.

## Features

- **4-dimension risk vector** (performance/groundedness, privacy,
  security, cost), each with visible sub-signals for explainability.
- **3 simulated use cases** with distinct, hot-loadable YAML policies:
  Customer Support, Internal Knowledge Assistant, Decision Support.
- **Deterministic detectors**: regex+Luhn PII detection, rule-based
  prompt-injection detection, retrieval-based groundedness/evidence
  checking against a small local knowledge base, and simulated
  cost/tool-call anomaly detection.
- **Consequence model**: severity × financial exposure × reversibility →
  LOW/MEDIUM/HIGH/CRITICAL tier, which can independently escalate a
  decision on top of the per-dimension thresholds.
- **Multi-turn / agent awareness**: conversation state is tracked; an
  unresolved evidence gap in an earlier turn escalates a later high-impact
  action to REVIEW even if that turn alone would have passed.
- **Human review workflow**: approve/edit/reject/escalate any decision;
  disagreement with ControlPlane's recommendation is recorded.
- **Explainability on every non-ALLOW decision**: what happened, why, why
  this specific action, and the evidence behind it.
- **Failsafe design**: `fail_open` vs `fail_closed` per policy — if
  ControlPlane itself fails, high-stakes policies fail closed.
- **Dashboard**: overview counts, risk distribution, cost telemetry
  (clearly labeled as simulated), a decisions table, and a detail view for
  every interaction.

## Demo scenarios

Full walkthrough in [docs/demo.md](docs/demo.md). Summary:

| # | Scenario | Expected result |
|---|----------|------------------|
| A | Plain FAQ question | ALLOW |
| B | Response contains an SSN | REDACT (redacted output shown) |
| C | Unsupported/contradicted high-stakes insurance claim | REVIEW or BLOCK |
| D | Agent makes 9 tool calls for a 1-call task | REROUTE or REVIEW (cost anomaly) |
| E | **Same claim, three use-case policies** | WARN / REVIEW / BLOCK — the core insight |

## Tech stack

- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLite (WAL mode)
- **Frontend**: single-file HTML/CSS/vanilla JS dashboard (no build step —
  chosen deliberately so a judge can open it with zero setup; see
  [docs/assumptions.md](docs/assumptions.md))
- **Policy config**: YAML, loaded and validated at runtime
- **Testing**: pytest (42 unit + integration + API tests)
- **Model layer**: provider abstraction with a deterministic mock provider
  so the whole prototype runs with **no paid API key required**

## Setup

Requires Python 3.10+.

```bash
git clone <this-repo>
cd controlplane
cp .env.example .env   # optional; defaults work out of the box
```

## Running locally

**One command:**

```bash
./run_demo.sh
```

This creates a virtualenv, installs dependencies, starts the API on
`localhost:8000`, and seeds the demo data. Then open `frontend/index.html`
directly in your browser.

**Manual steps:**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 seed_scenarios.py          # populate demo data
uvicorn app.main:app --reload --port 8000
```

Then open `frontend/index.html` in a browser (or `python3 -m http.server`
from the `frontend/` folder and visit `http://localhost:8000` — pick any
free port, e.g. 5500, and edit the `API` constant at the top of
`index.html` if you change the backend port).

API docs (Swagger UI): `http://localhost:8000/docs`

## Environment variables

See `.env.example`. `MODEL_PROVIDER=mock` remains available for deterministic rehearsal. Optional live Gemini mode is enabled with `GEMINI_API_KEY` and is used for semantic verification and the Generate + Protect flow. The decision engine remains deterministic and policy-driven.

## API examples

```bash
curl -X POST http://localhost:8000/interactions/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "Confirm the SSN on file: 123-45-6789",
    "ai_output": "Confirmed: SSN 123-45-6789 on file.",
    "context": {"use_case": "customer_support"}
  }'
```

```json
{
  "interaction_id": "a1b2c3d4e5f6",
  "risk": {"privacy": 1.0, "security": 0.0, "performance": 0.0, "cost": 0.0},
  "consequence": "medium",
  "decision": "redact",
  "reason": "privacy risk reached 'critical', requiring 'redact' under this policy.",
  "evidence": [],
  "redactions": [{"category": "ssn", "original_excerpt": "*******6789", "replacement": "[REDACTED_SSN]"}],
  "redacted_output": "Confirmed: SSN [REDACTED_SSN] on file.",
  "latency_ms": 1.2
}
```

Other endpoints: `GET /interactions`, `GET /interactions/{id}`,
`POST /interactions/{id}/review`, `GET /metrics`, `GET /policies`,
`GET /health`.

## Project structure

```
controlplane/
├── backend/
│   ├── app/
│   │   ├── api/         # FastAPI routes + request/response schemas
│   │   ├── context/      (context model lives in app/models/context.py)
│   │   ├── decision/     # consequence model, severity buckets, decision engine
│   │   ├── detectors/    # pii, injection, evidence, cost + aggregator
│   │   ├── models/       # Pydantic domain models
│   │   ├── policy/       # YAML policy loader/validator
│   │   ├── services/     # storage, evaluation orchestration, review, metrics, providers
│   │   └── main.py
│   ├── tests/            # 42 pytest tests (unit + integration + API)
│   ├── seed_scenarios.py
│   └── requirements.txt
├── frontend/
│   └── index.html        # single-file dashboard
├── data/
│   ├── policies/          customer_support.yaml, internal_knowledge.yaml, decision_support.yaml
│   └── knowledge/          kb.json (sample knowledge base)
├── docs/
│   ├── architecture.md
│   ├── assumptions.md
│   └── demo.md
├── run_demo.sh
├── .env.example
└── README.md
```

## Design decisions

- **Deterministic detectors before any LLM call.** All four detectors are
  regex/retrieval/arithmetic based — fast, explainable, and reproducible.
  No detector in this prototype makes an LLM call; the `ModelProvider`
  abstraction exists for the *application* side of the demo (the AI whose
  output ControlPlane evaluates), and only a deterministic mock provider
  is exercised, so the whole prototype is offline-runnable and
  reproducible.
- **Policy is data, not code.** Every threshold lives in YAML under
  `data/policies/`; changing enterprise risk appetite means editing a
  policy file, not the decision engine.
- **The decision engine is explicit application logic**, not a prompt. It
  picks the most restrictive of (per-dimension threshold actions,
  consequence-tier override) and always returns a structured explanation.
- **SQLite over Postgres/Redis** — demo-scale write volume doesn't justify
  the operational complexity of either.
- **Single-file HTML dashboard over a React build** — the brief's stack
  preference is React, but for a judge who needs to `open index.html` and
  see it work in one click, a build-free dashboard is more reliable. The
  README documents this trade-off rather than hiding it.

## Live Gemini mode

Set `GEMINI_API_KEY` and optionally `GEMINI_MODEL` in `.env`. The UI can generate an AI response and pass it through ControlPlane. For semantic grounding, ControlPlane retrieves trusted local evidence and asks Gemini for structured claim verdicts; Gemini does not choose the final business action. Without a key, the prototype remains runnable in deterministic fallback mode.

## Known limitations

- Risk scores are **not** scientifically validated safety guarantees.
- Groundedness/evidence checking is **probabilistic** (token-overlap
  retrieval + negation heuristics), not a guaranteed hallucination
  detector — see [docs/assumptions.md](docs/assumptions.md).
- Prompt-injection detection is demonstration-grade and not adversarially
  robust.
- Cost figures are simulated, not real provider billing.
- The knowledge base is 7 sample documents; retrieval quality will not
  generalize to a real enterprise corpus without a stronger retrieval
  layer.
- No authentication/authorization is implemented; this prototype is not
  intended to be exposed outside a local/demo environment.
- **ControlPlane itself is a sensitive system** — it sees raw AI inputs
  and outputs, including any PII before redaction. A production
  deployment needs its own access controls, encryption at rest, and audit
  logging around ControlPlane's own data store, not just the AI traffic it
  evaluates.

## Future roadmap

- Real model-provider integrations (OpenAI/Anthropic/Gemini) behind the
  existing `ModelProvider` abstraction.
- A learned/embedding-based retrieval layer once the knowledge base grows
  beyond what token-overlap similarity can handle well.
- Full feedback-loop analytics: aggregate human-override patterns to
  suggest policy threshold adjustments (currently only logged, not
  analyzed).
- Real enterprise IAM/SSO integration for the human review workflow.
- A proper frontend build (React) once the dashboard's interaction surface
  grows past what a single HTML file can cleanly support.
- Stronger, ML-assisted PII/injection detection layered on top of (not
  replacing) the current deterministic first pass.

---

*Built for Round 2 of the ControlPlane.ai competition. Uses simulated
data throughout; see [docs/assumptions.md](docs/assumptions.md) for a full
accounting of what is real versus simulated.*
