"""Pydantic data models used across the Ops Bot."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertSource(str, Enum):
    PROMETHEUS = "prometheus"
    CLOUDWATCH = "cloudwatch"
    GRAFANA = "grafana"
    MANUAL = "manual"


class RemediationActionType(str, Enum):
    RESTART_CONTAINER = "restart_container"
    RESTART_SERVICE = "restart_service"
    FLUSH_CACHE = "flush_cache"
    SCALE_OUT = "scale_out"
    NO_ACTION = "no_action"


class AlertPayload(BaseModel):
    alert_id: str = Field(..., description="Unique alert identifier")
    source: AlertSource = AlertSource.MANUAL
    service: str = Field(..., description="Affected service name")
    metric: str = Field(..., description="Metric that breached threshold")
    severity: Severity = Severity.MEDIUM
    summary: str = Field(..., description="Human-readable alert summary")
    labels: dict[str, str] = Field(default_factory=dict)
    fired_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict[str, Any] = Field(default_factory=dict)


class SystemContext(BaseModel):
    service: str
    logs: list[str] = Field(default_factory=list)
    stack_traces: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    recent_deployments: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    alert_id: str
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    remediation_action: RemediationActionType
    action_target: str | None = None
    action_params: dict[str, Any] = Field(default_factory=dict)
    incident_report_draft: str
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RemediationResult(BaseModel):
    action: RemediationActionType
    target: str | None = None
    success: bool
    message: str
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    dry_run: bool = False


class IncidentReport(BaseModel):
    incident_id: str
    alert_id: str
    service: str
    severity: Severity
    root_cause: str
    remediation: str
    timeline: list[str] = Field(default_factory=list)
    report_markdown: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
