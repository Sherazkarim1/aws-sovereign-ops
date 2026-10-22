from fastapi.testclient import TestClient

from src import main
from src.ai_analyzer import MockLLMClient
from src.log_collector import InMemoryLogSource
from src.models import AlertPayload


def _setup():
    main.reset_state()
    src = InMemoryLogSource()
    src.seed("payments", logs=["error: db timeout"], metrics={"error_rate": 0.2})
    main.set_log_source(src)


def test_health():
    _setup()
    client = TestClient(main.app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_webhook_alert_flow():
    _setup()
    client = TestClient(main.app)
    # inject mock llm by monkeypatching create_llm_client via app dependency? We'll patch analyze? Instead call endpoint with header and rely on mock provider default (mock)
    payload = {
        "alert_id": "a1",
        "service": "payments",
        "metric": "http_5xx",
        "severity": "high",
        "summary": "5xx spike",
    }
    r = client.post("/webhook/alert", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "incident_id" in data
    assert data["success"] is True


def test_incidents_list():
    _setup()
    client = TestClient(main.app)
    client.post("/webhook/alert", json={
        "alert_id": "a2", "service": "payments", "metric": "cpu", "summary": "cpu high",
    })
    r = client.get("/incidents")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_incident_not_found():
    _setup()
    client = TestClient(main.app)
    r = client.get("/incidents/NOPE")
    assert r.status_code == 404


def test_webhook_secret():
    import os
    os.environ["ALERT_WEBHOOK_SECRET"] = "secret"
    # reload settings? settings already loaded; manually set
    main.settings.alert_webhook_secret = "secret"
    _setup()
    client = TestClient(main.app)
    payload = {"alert_id": "a3", "service": "payments", "metric": "cpu", "summary": "x"}
    r = client.post("/webhook/alert", json=payload)
    assert r.status_code == 401
    r2 = client.post("/webhook/alert", json=payload, headers={"X-Webhook-Secret": "secret"})
    assert r2.status_code == 200
    main.settings.alert_webhook_secret = None
    os.environ.pop("ALERT_WEBHOOK_SECRET", None)
