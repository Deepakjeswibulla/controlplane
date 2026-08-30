import os

import pytest

from app.models.context import InteractionContext
from app.models.domain import ToolCall
from app.models.enums import ActionType, DecisionAction, UseCase
from app.services.evaluation import evaluate_interaction
from app.services.storage import Storage


@pytest.fixture
def storage(tmp_path):
    db_path = tmp_path / "test.db"
    return Storage(db_path=db_path)


def test_safe_faq_is_allowed(storage):
    ctx = InteractionContext(use_case=UseCase.CUSTOMER_SUPPORT)
    interaction = evaluate_interaction(
        storage,
        user_input="How do I reset my account password?",
        ai_output="You can reset your password from the login page by selecting Forgot password.",
        context=ctx,
    )
    assert interaction.decision.action == DecisionAction.ALLOW
    stored = storage.get_interaction(interaction.id)
    assert stored is not None
    assert stored.decision.action == DecisionAction.ALLOW


def test_pii_leakage_is_redacted(storage):
    ctx = InteractionContext(use_case=UseCase.CUSTOMER_SUPPORT)
    interaction = evaluate_interaction(
        storage,
        user_input="What's on file for SSN 123-45-6789?",
        ai_output="The account on file for SSN 123-45-6789 shows an active status.",
        context=ctx,
    )
    assert interaction.decision.action == DecisionAction.REDACT
    assert interaction.redacted_output is not None
    assert "123-45-6789" not in interaction.redacted_output


def test_unsupported_high_stakes_claim_goes_to_review(storage):
    ctx = InteractionContext(
        use_case=UseCase.DECISION_SUPPORT,
        action_type=ActionType.FINANCIAL_DECISION,
        financial_exposure_usd=15000,
    )
    interaction = evaluate_interaction(
        storage,
        user_input="Should we approve this claim under POL-2001 for ridesharing damage?",
        ai_output="Yes, POL-2001 covers damage that occurred while ridesharing.",
        context=ctx,
    )
    assert interaction.decision.action in (DecisionAction.REVIEW, DecisionAction.BLOCK)
    assert interaction.evidence  # evidence must be surfaced, even if contradicting


def test_agent_cost_anomaly_triggers_reroute_or_review(storage):
    ctx = InteractionContext(use_case=UseCase.INTERNAL_KNOWLEDGE, agent_mode=True)
    tool_calls = [ToolCall(name="search_kb", is_repeat=(i > 0)) for i in range(8)]
    interaction = evaluate_interaction(
        storage,
        user_input="Find the reimbursement limit.",
        ai_output="The limit is $500.",
        context=ctx,
        tool_calls=tool_calls,
        model_tier="large",
        request_complexity="simple",
    )
    assert interaction.decision.action in (DecisionAction.REROUTE, DecisionAction.REVIEW)
    assert interaction.cost_event.deviation_pct > 0


def test_missing_context_defaults_gracefully(storage):
    ctx = InteractionContext(use_case=UseCase.CUSTOMER_SUPPORT)
    interaction = evaluate_interaction(
        storage, user_input="", ai_output="", context=ctx
    )
    assert interaction.decision is not None


def test_empty_ai_output_does_not_crash(storage):
    ctx = InteractionContext(use_case=UseCase.INTERNAL_KNOWLEDGE)
    interaction = evaluate_interaction(
        storage, user_input="What is the policy?", ai_output="", context=ctx
    )
    assert interaction.decision is not None


def test_multi_turn_compounding_risk_escalates(storage):
    conv_id = "conv-test-1"
    ctx1 = InteractionContext(
        use_case=UseCase.DECISION_SUPPORT,
        conversation_id=conv_id,
        action_type=ActionType.INFORMATIONAL,
    )
    evaluate_interaction(
        storage,
        user_input="What does my policy cover?",
        ai_output="Your policy generally covers most incidents.",
        context=ctx1,
    )

    ctx2 = InteractionContext(
        use_case=UseCase.DECISION_SUPPORT,
        conversation_id=conv_id,
        action_type=ActionType.FINANCIAL_DECISION,
        financial_exposure_usd=5000,
    )
    turn2 = evaluate_interaction(
        storage,
        user_input="Approve the claim payout.",
        ai_output="Approving the claim payout based on the policy.",
        context=ctx2,
    )
    assert turn2.decision.action in (DecisionAction.REVIEW, DecisionAction.BLOCK)
    assert turn2.turn_number == 2


def test_human_review_disagreement_is_recorded(storage):
    from app.models.enums import ReviewOutcome
    from app.services.review import submit_review

    ctx = InteractionContext(use_case=UseCase.CUSTOMER_SUPPORT)
    interaction = evaluate_interaction(
        storage,
        user_input="SSN 123-45-6789",
        ai_output="Confirmed SSN 123-45-6789 on file.",
        context=ctx,
    )
    assert interaction.decision.action == DecisionAction.REDACT
    review = submit_review(storage, interaction, ReviewOutcome.REJECT, reviewer="tester")
    assert review.disagreement is True
