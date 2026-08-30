import logging
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.models.policy import Policy

logger = logging.getLogger("controlplane.policy")

_POLICY_DIR = Path(__file__).resolve().parents[3] / "data" / "policies"


class PolicyLoadError(Exception):
    pass


@lru_cache(maxsize=1)
def load_all_policies() -> dict[str, Policy]:
    """Loads every *.yaml file in data/policies keyed by use_case.
    Cached at process scope; call load_all_policies.cache_clear() to
    hot-reload during local development."""
    policies: dict[str, Policy] = {}
    if not _POLICY_DIR.exists():
        raise PolicyLoadError(f"Policy directory not found: {_POLICY_DIR}")

    for path in sorted(_POLICY_DIR.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            policy = Policy.model_validate(raw)
            policies[policy.use_case] = policy
        except (yaml.YAMLError, ValidationError) as exc:
            logger.error("Failed to load policy file %s: %s", path.name, exc)
            raise PolicyLoadError(f"Malformed policy file {path.name}: {exc}") from exc

    if not policies:
        raise PolicyLoadError("No valid policy files found")
    return policies


def get_policy(use_case: str) -> Policy:
    policies = load_all_policies()
    if use_case not in policies:
        raise PolicyLoadError(f"No policy configured for use case '{use_case}'")
    return policies[use_case]
