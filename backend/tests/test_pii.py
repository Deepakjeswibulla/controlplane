from app.detectors.pii import detect_pii, pii_score, redact


def test_detects_ssn():
    findings = detect_pii("My SSN is 123-45-6789.")
    assert any(f.category == "ssn" for f in findings)
    assert pii_score(findings) == 1.0


def test_detects_email():
    findings = detect_pii("Contact me at jane.doe@example.com")
    assert any(f.category == "email" for f in findings)


def test_no_false_positive_on_clean_text():
    findings = detect_pii("How do I reset my password?")
    assert findings == []
    assert pii_score(findings) == 0.0


def test_redaction_masks_ssn():
    text = "SSN: 123-45-6789 on file."
    redacted, redactions = redact(text, detect_pii(text))
    assert "123-45-6789" not in redacted
    assert "[REDACTED_SSN]" in redacted
    assert len(redactions) == 1


def test_credit_card_requires_luhn_validity():
    valid_cc = "4111111111111111"  # passes Luhn
    invalid_cc = "1234567890123456"  # fails Luhn
    assert any(f.category == "credit_card" for f in detect_pii(valid_cc))
    assert not any(f.category == "credit_card" for f in detect_pii(invalid_cc))
