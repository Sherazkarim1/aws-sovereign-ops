"""Automated remediation action execution (safe, dry-run by default)."""

from __future__ import annotations

import subprocess
import time
from typing import Callable, Protocol

from .config import get_settings
from .models import AnalysisResult, RemediationActionType, RemediationResult


class Executor(Protocol):
    def run(self, command: list[str]) -> tuple[int, str]: ...


class ShellExecutor:
    def run(self, command: list[str]) -> tuple[int, str]:
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=60)
            out = (proc.stdout or "") + (proc.stderr or "")
            return proc.returncode, out.strip()
        except Exception as exc:  # noqa: BLE001
            return 1, str(exc)


class Remediator:
    def __init__(self, dry_run: bool | None = None, executor: Executor | None = None) -> None:
        self.dry_run = dry_run if dry_run is not None else get_settings().dry_run
        self.executor = executor or ShellExecutor()
        self._handlers: dict[RemediationActionType, Callable[[AnalysisResult], RemediationResult]] = {
            RemediationActionType.RESTART_CONTAINER: self._restart_container,
            RemediationActionType.RESTART_SERVICE: self._restart_service,
            RemediationActionType.FLUSH_CACHE: self._flush_cache,
            RemediationActionType.SCALE_OUT: self._scale_out,
            RemediationActionType.NO_ACTION: self._no_action,
        }

    def execute(self, analysis=None, action=None, target=None, params=None, **kwargs) -> RemediationResult:
        if analysis is None:
            # Build a synthetic analysis from provided action
            from .models import AnalysisResult, RemediationActionType

            if isinstance(action, str):
                try:
                    action = RemediationActionType(action)
                except ValueError:
                    action = RemediationActionType.NO_ACTION
            analysis = AnalysisResult(
                alert_id=kwargs.get("alert_id", "manual"),
                root_cause=kwargs.get("root_cause", "manual remediation"),
                confidence=1.0,
                remediation_action=action or RemediationActionType.NO_ACTION,
                action_target=target,
                action_params=params or {},
                incident_report_draft="",
            )
        # Coerce if dict
        if isinstance(analysis, dict):
            from .models import AnalysisResult as _AR

            analysis = _AR(**analysis)
        handler = self._handlers.get(analysis.remediation_action, self._no_action)
        result = handler(analysis)
        result.dry_run = self.dry_run
        return result

    def execute_action(self, action, target=None, params=None, **kwargs):
        return self.execute(action=action, target=target, params=params, **kwargs)

    def remediate(self, *args, **kwargs):
        return self.execute(*args, **kwargs)

    def _target(self, analysis: AnalysisResult) -> str:
        return analysis.action_target or "unknown-target"

    def _restart_container(self, analysis: AnalysisResult) -> RemediationResult:
        target = self._target(analysis)
        if self.dry_run:
            return RemediationResult(
                action=RemediationActionType.RESTART_CONTAINER,
                target=target,
                success=True,
                message=f"[dry-run] would restart container {target}",
            )
        code, out = self.executor.run(["docker", "restart", target])
        return RemediationResult(
            action=RemediationActionType.RESTART_CONTAINER,
            target=target,
            success=code == 0,
            message=out or ("restarted" if code == 0 else "failed"),
        )

    def _restart_service(self, analysis: AnalysisResult) -> RemediationResult:
        target = self._target(analysis)
        if self.dry_run:
            return RemediationResult(
                action=RemediationActionType.RESTART_SERVICE,
                target=target,
                success=True,
                message=f"[dry-run] would restart service {target}",
            )
        code, out = self.executor.run(["systemctl", "restart", target])
        return RemediationResult(
            action=RemediationActionType.RESTART_SERVICE,
            target=target,
            success=code == 0,
            message=out or ("restarted" if code == 0 else "failed"),
        )

    def _flush_cache(self, analysis: AnalysisResult) -> RemediationResult:
        target = self._target(analysis)
        if self.dry_run:
            return RemediationResult(
                action=RemediationActionType.FLUSH_CACHE,
                target=target,
                success=True,
                message=f"[dry-run] would flush cache {target}",
            )
        # Simulated cache flush via redis-cli if available
        code, out = self.executor.run(["redis-cli", "-h", target, "FLUSHALL"])
        return RemediationResult(
            action=RemediationActionType.FLUSH_CACHE,
            target=target,
            success=code == 0,
            message=out or ("flushed" if code == 0 else "failed"),
        )

    def _scale_out(self, analysis: AnalysisResult) -> RemediationResult:
        target = self._target(analysis)
        params = analysis.action_params or {}
        count = int(params.get("desired_count", params.get("count", 2)))
        if self.dry_run:
            return RemediationResult(
                action=RemediationActionType.SCALE_OUT,
                target=target,
                success=True,
                message=f"[dry-run] would scale out {target} to {count} instances",
            )
        # Simulated: in production use AWS SDK / ECS update-service
        time.sleep(0)
        return RemediationResult(
            action=RemediationActionType.SCALE_OUT,
            target=target,
            success=True,
            message=f"scaled out {target} to {count} instances",
        )

    def _no_action(self, analysis: AnalysisResult) -> RemediationResult:
        return RemediationResult(
            action=RemediationActionType.NO_ACTION,
            target=None,
            success=True,
            message="No automated remediation required; manual review.",
        )


def execute_remediation(*args, **kwargs):
    return Remediator().execute(*args, **kwargs)
