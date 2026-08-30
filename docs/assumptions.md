# Assumptions & Simplifications

This document exists so the design choices below can be defended directly
in Q&A rather than discovered as surprises.

## Data & policy
- **Simulated enterprise policies.** The three YAML policy files in
  `data/policies/` are illustrative, not derived from a real customer's
  governance rules. Thresholds (which severity maps to which action) were
  chosen to make the "same risk, different context" story clear for a demo,
  not validated against real incident data.
- **Sample knowledge base.** `data/knowledge/kb.json` contains 7 short
  hand-written documents covering the three demo use cases. A production
  system would connect to the enterprise's actual document store.
- **Simulated cost pricing.** Token prices in `app/detectors/cost.py` are
  illustrative per-1K-token constants, not real provider billing rates.
  "Estimated savings" shown on the dashboard are computed from these
  simulated figures and are explicitly labeled as simulated in the API
  response and UI — never presented as a real dollar figure.

## Detectors
- **PII detection is regex + Luhn-check based**, not a full NER/DLP
  pipeline. It reliably catches the demo's SSN/email/phone/credit-card/
  policy-ID patterns but will miss more obfuscated or context-dependent PII
  (e.g. a name + address combination without a structured identifier).
- **Groundedness/evidence checking uses Jaccard token-overlap retrieval**
  over the local knowledge base plus a small negation-cue heuristic to
  distinguish "claim asserts coverage" from "document excludes it." This is
  a deliberately lightweight, explainable substitute for a full NLI/
  entailment model or an LLM-as-judge. It will not catch subtle factual
  errors that don't show up as vocabulary overlap or an explicit negation
  cue, and it is tuned (similarity thresholds) against the demo scenarios,
  not a labeled evaluation set.
- **Prompt-injection detection is a rule/regex list** covering a handful of
  common attack phrasings. It is explicitly a demonstration-grade detector,
  not an adversarially robust classifier — a determined attacker could
  trivially rephrase around these rules.
- **Cost telemetry is entirely simulated.** Token counts, model tiers, tool
  call counts, and retries are supplied by the caller (or the seed script)
  rather than measured from a real model provider, since the prototype is
  designed to run without any paid API key.

## Consequence model
- `consequence = f(severity, financial_exposure, reversibility)` is an
  engineering heuristic built for this prototype's demo scenarios. It is
  not a scientifically validated risk-scoring formula and should not be
  read as one.

## Context model
- `InteractionContext` implements only the fields that materially change a
  decision in this prototype (use case, action type, reversibility,
  financial exposure, role, conversation id, agent mode, geography,
  domain). A production system would likely add many more dimensions
  (data residency, customer tier, model version, etc.).

## Multi-turn / agent behavior
- The compounding-risk rule (`app/services/evaluation.py`,
  `_load_conversation_state`) is a single hand-written heuristic: if any
  prior turn in the conversation had performance risk ≥ 0.6 and the current
  turn attempts a financial-decision or agent-tool-action, the decision is
  escalated to REVIEW. This demonstrates the concept of workflow-aware
  decisions; a production system would need a richer state machine.

## Providers
- Only a deterministic `MockProvider` is wired up and exercised by tests.
  The `ModelProvider` abstraction includes stubs for real providers
  (OpenAI/Anthropic/Gemini) but they intentionally raise until API keys and
  real client code are added — the prototype never silently pretends to
  call a real model.

## Scale
- SQLite with WAL mode is used for storage. This is appropriate for
  demo-scale traffic (dozens to low hundreds of interactions) and is not a
  claim about production scalability.

## What is NOT built (see README roadmap)
ML retraining/fine-tuning pipelines, a real vector database, Kubernetes or
other distributed infrastructure, real enterprise IAM/SSO, and compliance
certification are all out of scope for Round 2 and are documented as future
roadmap items rather than attempted.
