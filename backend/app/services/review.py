from datetime import datetime, timezone

from app.models.domain import HumanReview, Interaction
from app.models.enums import ReviewOutcome
from app.services.storage import Storage

_AGREEMENT_MAP = {
    ReviewOutcome.APPROVE: {"allow", "warn"},
    ReviewOutcome.EDIT: {"edit", "redact"},
    ReviewOutcome.REJECT: {"block"},
    ReviewOutcome.ESCALATE: {"review", "reroute"},
}


def submit_review(
    storage: Storage,
    interaction: Interaction,
    outcome: ReviewOutcome,
    reviewer: str,
    notes: str | None = None,
) -> HumanReview:
    recommendation = interaction.decision.action if interaction.decision else None
    disagreement = (
        recommendation is not None
        and recommendation.value not in _AGREEMENT_MAP.get(outcome, set())
    )

    review = HumanReview(
        interaction_id=interaction.id,
        outcome=outcome,
        reviewer=reviewer,
        notes=notes,
        controlplane_recommendation=recommendation,
        disagreement=disagreement,
        resolved_at=datetime.now(timezone.utc),
    )
    interaction.human_review = review
    storage.save_interaction(interaction)
    return review
