# Architecture

```
                    POST /interactions/evaluate
                              |
                              v
                    +-------------------+
                    |  Detector layer   |   (parallel-safe, all deterministic/local)
                    |-------------------|
                    | PII (regex+Luhn)  |
                    | Injection (rules) |
                    | Evidence (retrv.) |
                    | Cost (telemetry)  |
                    +-------------------+
                              |
                              v
                    +-------------------+
                    |  Risk aggregator   |  -> RiskSignal per dimension
                    |  (4-dim vector)    |     {performance, privacy, security, cost}
                    +-------------------+
                              |
              +---------------+----------------+
              v                                 v
    +-------------------+            +-------------------+
    | Consequence model  |            |  Policy engine     |
    | severity x exposure|            |  (YAML, per use    |
    | x reversibility    |            |  case, hot-loadable)|
    +-------------------+            +-------------------+
              |                                 |
              +---------------+----------------+
                              v
                    +-------------------+
                    |  Decision engine   |  -> Decision(action, reason,
                    |  (deterministic)   |     what/why/why-this-action)
                    +-------------------+
                              |
                    +---------+---------+
                    v                   v
            Redaction applied     Persisted (SQLite)
            if action=REDACT      + conversation state
                                   updated for multi-turn
                                   compounding-risk checks
```

## Module boundaries (backend/app)

- `models/` — Pydantic domain models (Interaction, RiskSignal, Decision,
  Policy, Context, HumanReview, CostEvent, etc). No business logic.
- `detectors/` — Each detector is a pure function: text/telemetry in,
  `Signal` list out. `aggregator.py` composes them into the 4-dimension
  risk vector. Detectors have no knowledge of policy or decisions.
- `policy/` — Loads and validates YAML policy files into `Policy` models.
  Cached at process scope.
- `decision/` — `consequence.py` computes the consequence tier;
  `severity.py` buckets a 0–1 score into low/medium/high/critical;
  `engine.py` combines risk + policy + consequence into a `Decision`.
  Pure functions, no I/O.
- `services/` — Orchestration and side effects: `evaluation.py` runs the
  full pipeline and handles multi-turn state; `storage.py` is the SQLite
  layer; `review.py` handles human review; `metrics.py` aggregates for the
  dashboard; `providers.py` is the model-provider abstraction.
- `api/` — FastAPI routes and request/response schemas only; no business
  logic lives here.

This separation means each detector, the policy engine, and the decision
engine can be tested and replaced independently (see `tests/`).

## Why no vector DB / message broker / Kubernetes
Round 2 explicitly permits a simplified, non-production prototype. The
knowledge base is 7 short documents — a Jaccard-similarity retrieval over
an in-memory list is faster and more explainable than a vector index at
this scale, and there is nothing here that benefits from distributed
infrastructure. See `docs/assumptions.md` and the README roadmap for what a
production version would add.

## Performance choices
- All detectors are deterministic (regex, retrieval, arithmetic) and run
  in well under a millisecond each; there is no LLM call on the hot path,
  so there was no benefit to async/parallel execution for this workload —
  adding it would be complexity without a measurable win (see
  `detectors/aggregator.py` docstring).
- Policies are loaded once and cached (`functools.lru_cache`); the cache
  can be cleared for local hot-reloading during development.
- The knowledge base is loaded once and cached the same way.
