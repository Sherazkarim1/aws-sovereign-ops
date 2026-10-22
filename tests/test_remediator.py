from src.ai_analyzer import MockLLMClient
from src.models import AnalysisResult, RemediationActionType
from src.remediator import Remediator


def _analysis(action=RemediationActionType.RESTART_CONTAINER, target="svc"):
    return AnalysisResult(
        alert_id="a1",
        root_cause="x",
        confidence=0.9,
        remediation_action=action,
        action_target=target,
        incident_report_draft="d",
    )


def test_dry_run_restart():
    r = Remediator(dry_run=True)
    res = r.execute(_analysis())
    assert res.success is True
    assert res.dry_run is True
    assert "dry-run" in res.message


def test_no_action():
    r = Remediator(dry_run=True)
    res = r.execute(_analysis(action=RemediationActionType.NO_ACTION))
    assert res.action == RemediationActionType.NO_ACTION
    assert res.success is True


def test_scale_out_params():
    a = _analysis(action=RemediationActionType.SCALE_OUT, target="web")
    a.action_params = {"desired_count": 4}
    r = Remediator(dry_run=True)
    res = r.execute(a)
    assert "4" in res.message


def test_flush_cache_dry():
    r = Remediator(dry_run=True)
    res = r.execute(_analysis(action=RemediationActionType.FLUSH_CACHE, target="redis"))
    assert res.success is True
    assert res.target == "redis"
