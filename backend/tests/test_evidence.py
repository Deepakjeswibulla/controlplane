from app.detectors.evidence import check_groundedness, evidence_score


def test_supported_claim():
    verdict, signals, evidence = check_groundedness(
        "You can reset your password from the login page.", "customer_support"
    )
    assert verdict in ("SUPPORTED", "WEAKLY_SUPPORTED")
    assert evidence


def test_contradicted_claim():
    verdict, signals, evidence = check_groundedness(
        "Yes, policy POL-1001 covers flood damage to your basement.", "decision_support"
    )
    assert verdict == "CONTRADICTED"
    assert evidence_score(verdict) == 1.0


def test_unsupported_claim_no_kb_match():
    verdict, signals, evidence = check_groundedness(
        "The moon landing was staged by aliens.", "decision_support"
    )
    assert verdict == "UNSUPPORTED"


def test_evidence_score_ordering():
    assert evidence_score("SUPPORTED") < evidence_score("WEAKLY_SUPPORTED")
    assert evidence_score("WEAKLY_SUPPORTED") < evidence_score("UNSUPPORTED")
    assert evidence_score("UNSUPPORTED") < evidence_score("CONTRADICTED")
