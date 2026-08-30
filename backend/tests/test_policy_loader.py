import pytest
import yaml

from app.policy.loader import PolicyLoadError, get_policy, load_all_policies
from app.models.policy import Policy


def test_loads_all_three_policies():
    load_all_policies.cache_clear()
    policies = load_all_policies()
    assert set(policies) == {"customer_support", "internal_knowledge", "decision_support"}


def test_get_policy_returns_expected_fail_mode():
    load_all_policies.cache_clear()
    assert get_policy("decision_support").fail_mode.value == "fail_closed"
    assert get_policy("customer_support").fail_mode.value == "fail_open"


def test_get_policy_missing_use_case_raises():
    load_all_policies.cache_clear()
    with pytest.raises(PolicyLoadError):
        get_policy("nonexistent_use_case")


def test_malformed_policy_severity_level_rejected():
    with pytest.raises(Exception):
        Policy.model_validate(
            {
                "policy_id": "bad",
                "use_case": "bad_case",
                "thresholds": {"performance": {"not_a_level": "block"}},
            }
        )
