import tempfile

from src.ai_analyzer import MockLLMClient, analyze
from src.incident_report import generate_report, persist_report
from src.log_collector import collect_context
from src.models import AlertPayload, RemediationActionType
from src.remediator import Remediator


def test_generate_report_markdown():
    alert = AlertPayload(alert_id="a1", service="svc", metric="cpu", summary="high")
    ctx = collect_context("svc")
    analysis = analyze(alert, ctx, client=MockLLMClient())
    rem = Remediator(dry_run=True).execute(analysis)
    report = generate_report(alert, analysis, rem)
    assert report.incident_id.startswith("INC-")
    assert "Incident Report" in report.report_markdown
    assert alert.service in report.report_markdown


def test_persist_report():
    alert = AlertPayload(alert_id="a2", service="svc", metric="cpu", summary="high")
    ctx = collect_context("svc")
    analysis = analyze(alert, ctx, client=MockLLMClient())
    rem = Remediator(dry_run=True).execute(analysis)
    report = generate_report(alert, analysis, rem)
    with tempfile.TemporaryDirectory() as d:
        path = persist_report(report, d)
        assert path.endswith(".md")
        with open(path) as f:
            assert "Incident Report" in f.read()
