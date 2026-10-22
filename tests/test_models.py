from src.models import AlertPayload, Severity, AlertSource


def test_alert_defaults():
    a = AlertPayload(alert_id="a1", service="svc", metric="cpu", summary="high cpu")
    assert a.severity == Severity.MEDIUM
    assert a.source == AlertSource.MANUAL
    assert a.labels == {}


def test_severity_values():
    assert Severity.CRITICAL.value == "critical"
