"""FastAPI webhook receiver for SovereignGuard Ops Bot."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from .ai_analyzer import LLMClient, analyze, create_llm_client
from .config import get_settings
from .incident_report import generate_report, persist_report
from .log_collector import InMemoryLogSource, collect_context
from .models import AlertPayload, AnalysisResult, IncidentReport, RemediationResult
from .remediator import Remediator

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")

_INCIDENTS: list[IncidentReport] = []
_LOG_SOURCE = InMemoryLogSource()
_LLM_CLIENT: LLMClient | None = None


def get_log_source():
    return _LOG_SOURCE


def set_log_source(source) -> None:
    global _LOG_SOURCE
    _LOG_SOURCE = source


def get_llm_client() -> LLMClient | None:
    return _LLM_CLIENT


def set_llm_client(client: LLMClient | None) -> None:
    global _LLM_CLIENT
    _LLM_CLIENT = client


def _verify_secret(x_webhook_secret: str | None) -> None:
    expected = settings.alert_webhook_secret
    if expected and x_webhook_secret != expected:
        raise HTTPException(status_code=401, detail="invalid webhook secret")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.post("/webhook/alert")
def handle_alert(
    alert: AlertPayload,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> JSONResponse:
    _verify_secret(x_webhook_secret)
    context = collect_context(alert.service, get_log_source())
    analysis: AnalysisResult = analyze(alert, context, client=get_llm_client() or create_llm_client(settings))
    remediator = Remediator(dry_run=settings.dry_run)
    remediation: RemediationResult = remediator.execute(analysis)
    report = generate_report(alert, analysis, remediation)
    try:
        persist_report(report, settings.incident_report_dir)
    except OSError:
        pass
    _INCIDENTS.append(report)
    return JSONResponse(
        status_code=200,
        content={
            "alert_id": alert.alert_id,
            "incident_id": report.incident_id,
            "root_cause": analysis.root_cause,
            "remediation": remediation.message,
            "success": remediation.success,
        },
    )


@app.get("/incidents")
def list_incidents() -> list[dict[str, Any]]:
    return [r.model_dump(mode="json") for r in _INCIDENTS]


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict[str, Any]:
    for r in _INCIDENTS:
        if r.incident_id == incident_id:
            return r.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="incident not found")


@app.post("/remediate")
def manual_remediate(analysis: AnalysisResult) -> dict[str, Any]:
    remediator = Remediator(dry_run=settings.dry_run)
    result = remediator.execute(analysis)
    return result.model_dump(mode="json")


def reset_state() -> None:
    global _INCIDENTS
    _INCIDENTS = []
    set_log_source(InMemoryLogSource())
    set_llm_client(None)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
