import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import storage as storage_module


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    db_path = tmp_path / "api_test.db"
    monkeypatch.setattr(storage_module, "_storage_instance", None)
    original = storage_module.Storage
    monkeypatch.setattr(
        storage_module, "Storage", lambda db_path=db_path: original(db_path=db_path)
    )
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_evaluate_allow_case(client):
    resp = client.post(
        "/interactions/evaluate",
        json={
            "user_input": "How do I reset my password?",
            "ai_output": "Reset it from the login page via Forgot password.",
            "context": {"use_case": "customer_support"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "allow"
    assert "interaction_id" in body


def test_evaluate_redacts_pii(client):
    resp = client.post(
        "/interactions/evaluate",
        json={
            "user_input": "My SSN is 123-45-6789",
            "ai_output": "Noted, SSN 123-45-6789 saved.",
            "context": {"use_case": "customer_support"},
        },
    )
    body = resp.json()
    assert body["decision"] == "redact"
    assert "123-45-6789" not in (body["redacted_output"] or "")


def test_get_interaction_not_found(client):
    resp = client.get("/interactions/does-not-exist")
    assert resp.status_code == 404


def test_list_interactions_and_metrics(client):
    client.post(
        "/interactions/evaluate",
        json={
            "user_input": "hello",
            "ai_output": "hi there",
            "context": {"use_case": "customer_support"},
        },
    )
    listing = client.get("/interactions")
    assert listing.status_code == 200
    assert len(listing.json()) >= 1

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "decisions" in metrics.json()


def test_policies_endpoint(client):
    resp = client.get("/policies")
    assert resp.status_code == 200
    assert set(resp.json()) == {"customer_support", "internal_knowledge", "decision_support"}


def test_review_endpoint(client):
    eval_resp = client.post(
        "/interactions/evaluate",
        json={
            "user_input": "SSN 123-45-6789",
            "ai_output": "Confirmed SSN 123-45-6789",
            "context": {"use_case": "customer_support"},
        },
    )
    interaction_id = eval_resp.json()["interaction_id"]
    review_resp = client.post(
        f"/interactions/{interaction_id}/review",
        json={"outcome": "approve", "reviewer": "judge"},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["disagreement"] is True  # redact != approve
