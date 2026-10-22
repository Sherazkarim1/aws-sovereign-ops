"""Collects logs and stack traces for a given service.

In production this would query CloudWatch Logs, Loki, or the container
runtime. Here we expose a pluggable interface so tests can inject data.
"""

from __future__ import annotations

from typing import Protocol

from .models import SystemContext


class LogSource(Protocol):
    def fetch_logs(self, service: str, limit: int = 100) -> list[str]: ...
    def fetch_stack_traces(self, service: str) -> list[str]: ...
    def fetch_metrics(self, service: str) -> dict[str, float]: ...
    def fetch_recent_deployments(self, service: str) -> list[str]: ...


class InMemoryLogSource:
    """Default in-memory log source used for demos and tests."""

    def __init__(self) -> None:
        self._logs: dict[str, list[str]] = {}
        self._traces: dict[str, list[str]] = {}
        self._metrics: dict[str, dict[str, float]] = {}
        self._deployments: dict[str, list[str]] = {}

    def seed(self, service: str, logs=None, traces=None, metrics=None, deployments=None) -> None:
        if logs is not None:
            self._logs[service] = list(logs)
        if traces is not None:
            self._traces[service] = list(traces)
        if metrics is not None:
            self._metrics[service] = dict(metrics)
        if deployments is not None:
            self._deployments[service] = list(deployments)

    def fetch_logs(self, service: str, limit: int = 100) -> list[str]:
        return list(self._logs.get(service, []))[-limit:]

    def fetch_stack_traces(self, service: str) -> list[str]:
        return list(self._traces.get(service, []))

    def fetch_metrics(self, service: str) -> dict[str, float]:
        return dict(self._metrics.get(service, {}))

    def fetch_recent_deployments(self, service: str) -> list[str]:
        return list(self._deployments.get(service, []))


def collect_context(service: str, source: LogSource | None = None) -> SystemContext:
    src = source or InMemoryLogSource()
    return SystemContext(
        service=service,
        logs=src.fetch_logs(service),
        stack_traces=src.fetch_stack_traces(service),
        metrics=src.fetch_metrics(service),
        recent_deployments=src.fetch_recent_deployments(service),
    )


def collect_logs(service, source=None):
    return collect_context(service, source).logs
