from collections import Counter

from app.services.storage import Storage


def compute_metrics(storage: Storage) -> dict:
    interactions = storage.list_interactions(limit=1000)
    total = len(interactions)
    action_counts = Counter(
        i.decision.action.value for i in interactions if i.decision
    )

    risk_totals = {"performance": 0.0, "privacy": 0.0, "security": 0.0, "cost": 0.0}
    for i in interactions:
        for dim, signal in i.risk.items():
            if dim in risk_totals:
                risk_totals[dim] += signal.score
    risk_avg = {k: round(v / total, 3) if total else 0.0 for k, v in risk_totals.items()}

    expected_cost = sum(i.cost_event.expected_cost_usd for i in interactions if i.cost_event)
    actual_cost = sum(i.cost_event.actual_cost_usd for i in interactions if i.cost_event)
    anomalies = sum(
        1
        for i in interactions
        if i.risk.get("cost") and i.risk["cost"].signals
    )

    return {
        "total_interactions": total,
        "decisions": {
            "allow": action_counts.get("allow", 0),
            "warn": action_counts.get("warn", 0),
            "edit": action_counts.get("edit", 0),
            "redact": action_counts.get("redact", 0),
            "reroute": action_counts.get("reroute", 0),
            "review": action_counts.get("review", 0),
            "block": action_counts.get("block", 0),
        },
        "average_risk": risk_avg,
        "cost_telemetry": {
            "expected_cost_usd": round(expected_cost, 4),
            "actual_cost_usd": round(actual_cost, 4),
            "anomaly_count": anomalies,
            "estimated_savings_usd_simulated": round(max(actual_cost - expected_cost, 0), 4),
            "note": "All cost figures are simulated for demo purposes and not real provider billing.",
        },
    }
