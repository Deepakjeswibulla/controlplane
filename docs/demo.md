# Demo Walkthrough

Run `./run_demo.sh` (or the manual steps in the README) first, then open
`frontend/index.html` in a browser with the backend running on
`localhost:8000`.

## Scenario 1 — Safe request → ALLOW
Click **A · Safe request**. A plain password-reset FAQ answer has no PII,
no injection pattern, and is well supported by the knowledge base, so it
is allowed immediately.

## Scenario 2 — PII leakage → REDACT
Click **B · PII leakage**. The AI output contains an SSN and an email
address. ControlPlane detects both, classifies privacy risk as CRITICAL,
and shows the redacted output with the sensitive values replaced before
the response would reach the user.

## Scenario 3 — Unsupported high-stakes claim → REVIEW/BLOCK
Click **C · Unsupported high-stakes claim**. The AI claims a policy covers
ridesharing damage; the retrieved policy document says the opposite. Under
the `decision_support` policy (high consequence, `fail_closed`), this
contradiction routes to human review or is blocked outright — click the
row to see the actual evidence document and similarity score.

## Scenario 4 — Agent cost anomaly → REROUTE/REVIEW
Click **D · Agent cost anomaly**. A simulated agent makes 9 tool calls
(mostly repeats) for a simple lookup that should take ~1. ControlPlane
flags excessive tool calls, repeated identical calls, and a cost deviation,
and stops the loop.

## Scenario 5 — THE core insight: same risk, different context
Click **Run "same claim, three contexts"**. The exact same unsupported
insurance claim is evaluated three times, once per use case:
- Customer Support → **WARN** (low consequence, informational)
- Internal Knowledge → **REVIEW** (employees may act on it)
- Decision Support → **BLOCK** (high financial exposure, irreversible
  action, contradicts the retrieved policy document)

This is the product's central claim: **the risk signal is the same; the
decision differs because ControlPlane accounts for context, consequence,
and policy.**

## Multi-turn compounding risk (seeded automatically)
Open the "Recent decisions" table and look for the two `decision_support`
rows sharing a conversation: turn 1 gives an ambiguous answer, turn 2
attempts to approve a $5,000 claim payout. ControlPlane recognizes the
unresolved uncertainty from turn 1 and does not let the high-impact action
in turn 2 pass silently.

## Human review + feedback loop
`POST /interactions/{id}/review` lets a reviewer approve, edit, reject, or
escalate any decision. If the human's outcome doesn't match ControlPlane's
recommendation, `disagreement: true` is recorded — the foundation for a
future analytics/feedback loop (see README roadmap).
