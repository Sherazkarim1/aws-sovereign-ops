import json

from src.ai_analyzer import (
    MockLLMClient,
    _extract_json,
    analyze,
    build_prompt,
)
from src.log_collector import InMemoryLogSource, collect_context
from src.models import AlertPayload, RemediationActionType, Severity


def _alert():
    return AlertPayload(alert_id="alert-1", service="payments", metric="http_5xx", summary="5xx spike", severity=Severity.HIGH)


def test_build_prompt_contains_alert():
    alert = _alert()
    ctx = collect_context("payments")
    prompt = build_prompt(alert, ctx)
    assert "payments" in prompt
    assert "http_5xx" in prompt


def test_extract_json_plain():
    data = _extract_json('{"root_cause": "x", "confidence": 0.9}')
    assert data["root_cause"] == "x"


def test_extract_json_fenced():
    text = "```json\n{\"a\": 1}\n```"
    assert _extract_json(text) == {"a": 1}


def test_analyze_with_mock_response():
    alert = _alert()
    ctx = collect_context("payments")
    client = MockLLMClient(response={
        "root_cause": "db connection pool exhausted",
        "confidence": 0.92,
        "remediation_action": "restart_container",
        "action_target": "payments",
        "action_params": {},
        "incident_report_draft": "draft",
    })
    result = analyze(alert, ctx, client=client)
    assert result.root_cause == "db connection pool exhausted"
    assert result.remediation_action == RemediationActionType.RESTART_CONTAINER
    assert result.confidence == 0.92


def test_analyze_heuristic_memory():
    alert = AlertPayload(alert_id="a2", service="api", metric="memory", summary="memory leak")
    src = InMemoryLogSource()
    src.seed("api", logs=["OOM killed"], metrics={"memory_pct": 95.0})
    ctx = collect_context("api", src)
    client = MockLLMClient()  # heuristic
    result = analyze(alert, ctx, client=client)
    assert result.remediation_action in (RemediationActionType.RESTART_SERVICE, RemediationActionType.RESTART_CONTAINER)


def test_mock_client_returns_json():
    c = MockLLMClient()
    out = c.complete("memory leak high cpu")
    data = json.loads(out)
    assert "root_cause" in data
