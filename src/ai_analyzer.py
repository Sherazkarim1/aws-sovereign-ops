"""LLM integration: prompt templates, provider abstraction, analysis logic."""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any

from .config import Settings, get_settings
from .models import (
    AlertPayload,
    AnalysisResult,
    RemediationActionType,
    SystemContext,
)


ROOT_CAUSE_PROMPT = """You are an expert Site Reliability Engineer and incident responder.

An alert has fired for a production service. Analyze the provided context and
respond ONLY with a valid JSON object (no markdown, no commentary) matching:

{{
  "root_cause": "<concise root cause explanation>",
  "confidence": <float 0.0-1.0>,
  "remediation_action": "<one of: restart_container | restart_service | flush_cache | scale_out | no_action>",
  "action_target": "<service/container/instance group to act on or null>",
  "action_params": {{}},
  "incident_report_draft": "<short markdown incident summary>"
}}

ALERT:
id: {alert_id}
service: {service}
metric: {metric}
severity: {severity}
summary: {summary}
fired_at: {fired_at}

SYSTEM CONTEXT:
logs:
{logs}

stack_traces:
{traces}

metrics:
{metrics}

recent_deployments:
{deployments}
"""


def _format_list(items: list[str]) -> str:
    if not items:
        return "  (none)"
    return "\n".join(f"  - {i}" for i in items)


def _format_metrics(m: dict[str, float]) -> str:
    if not m:
        return "  (none)"
    return "\n".join(f"  - {k}: {v}" for k, v in m.items())


def build_prompt(alert, context=None, logs=None, **kwargs):
    alert = _coerce_alert(alert)
    if context is None and "context" in kwargs:
        context = kwargs.pop("context")
    svc = getattr(alert, "service", None)
    ctx = _coerce_context(context, logs=logs, service=svc)
    return ROOT_CAUSE_PROMPT.format(
        alert_id=alert.alert_id,
        service=alert.service,
        metric=alert.metric,
        severity=alert.severity.value,
        summary=alert.summary,
        fired_at=alert.fired_at.isoformat(),
        logs=_format_list(ctx.logs),
        traces=_format_list(ctx.stack_traces),
        metrics=_format_metrics(ctx.metrics),
        deployments=_format_list(ctx.recent_deployments),
    )


class LLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return raw text completion for the given prompt."""


class MockLLMClient(LLMClient):
    """Deterministic mock used in tests and dry runs."""

    def __init__(self, response: dict[str, Any] | str | None = None) -> None:
        self.response = response

    def complete(self, prompt: str) -> str:
        if self.response is None:
            # Heuristic default based on prompt keywords
            action = "restart_container"
            root = "Service unhealthy; restarting container to restore availability."
            import re as _re

            _lowered = prompt.lower()
            if _re.search(r"\b(memory|leak|oom)\b", _lowered):
                action = "restart_service"
                root = "Memory leak detected in service process; restart required."
            elif _re.search(r"\bcache\b", _lowered):
                action = "flush_cache"
                root = "Stale cache entries causing elevated error rate."
            elif _re.search(r"\bcpu\b", _lowered) and "scale" in _lowered:
                action = "scale_out"
                root = "CPU saturation; scale out instance group."
            payload = {
                "root_cause": root,
                "confidence": 0.85,
                "remediation_action": action,
                "action_target": None,
                "action_params": {},
                "incident_report_draft": f"## Incident\n\n{root}\n",
            }
            return json.dumps(payload)
        if isinstance(self.response, str):
            return self.response
        return json.dumps(self.response)


class AnthropicLLMClient(LLMClient):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model or "claude-3-5-sonnet-20241022"

    def complete(self, prompt: str) -> str:
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text if msg.content else ""


class BedrockLLMClient(LLMClient):
    def __init__(self, region: str | None = None, model_id: str | None = None) -> None:
        import boto3

        self._client = boto3.client("bedrock-runtime", region_name=region or "us-east-1")
        self.model_id = model_id or "anthropic.claude-3-5-sonnet-20241022-v2:0"

    def complete(self, prompt: str) -> str:
        import json as _json

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = self._client.invoke_model(modelId=self.model_id, body=_json.dumps(body))
        payload = _json.loads(resp["body"].read())
        return payload["content"][0]["text"]


def create_llm_client(settings: Settings | None = None, client: LLMClient | None = None) -> LLMClient:
    if client is not None:
        return client
    s = settings or get_settings()
    if s.llm_provider == "anthropic":
        return AnthropicLLMClient(api_key=s.anthropic_api_key, model=s.anthropic_model)
    if s.llm_provider == "bedrock":
        return BedrockLLMClient(region=s.bedrock_region, model_id=s.bedrock_model_id)
    return MockLLMClient()


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Strip markdown code fences if present
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _coerce_action(value: Any) -> RemediationActionType:
    try:
        return RemediationActionType(value)
    except ValueError:
        return RemediationActionType.NO_ACTION


def _coerce_alert(alert):
    if isinstance(alert, AlertPayload):
        return alert
    if isinstance(alert, dict):
        return AlertPayload(**alert)
    return alert


def _coerce_context(context, logs=None, service=None):
    if isinstance(context, SystemContext):
        return context
    if isinstance(context, list):
        svc = service or "unknown"
        return SystemContext(service=svc, logs=list(context))
    if isinstance(context, str):
        svc = service or "unknown"
        return SystemContext(service=svc, logs=[context])
    if context is None:
        svc = service or "unknown"
        ctx_logs = list(logs) if logs is not None else []
        return SystemContext(service=svc, logs=ctx_logs)
    if isinstance(context, dict):
        return SystemContext(**context)
    return context


def analyze(alert, context=None, client=None, llm_client=None, logs=None, **kwargs) -> AnalysisResult:
    alert = _coerce_alert(alert)
    if context is None and "context" in kwargs:
        context = kwargs.pop("context")
    svc = getattr(alert, "service", None)
    context = _coerce_context(context, logs=logs, service=svc)
    settings = get_settings()
    llm = client or llm_client or create_llm_client(settings)
    prompt = build_prompt(alert, context)
    raw = llm.complete(prompt)
    data = _extract_json(raw)
    return AnalysisResult(
        alert_id=alert.alert_id,
        root_cause=str(data.get("root_cause", "Unknown root cause")),
        confidence=float(data.get("confidence", 0.5)),
        remediation_action=_coerce_action(data.get("remediation_action", "no_action")),
        action_target=data.get("action_target"),
        action_params=data.get("action_params") or {},
        incident_report_draft=str(data.get("incident_report_draft", "")),
    )


def analyze_alert(alert, logs=None, client=None, **kwargs):
    return analyze(alert, logs=logs, client=client, **kwargs)
