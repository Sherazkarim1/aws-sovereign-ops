"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Settings:
    app_name: str = "SovereignGuard Ops Bot"
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))
    anthropic_api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"))
    bedrock_region: str = field(default_factory=lambda: os.getenv("BEDROCK_REGION", "us-east-1"))
    bedrock_model_id: str = field(default_factory=lambda: os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"))

    dry_run: bool = field(default_factory=lambda: os.getenv("DRY_RUN", "true").lower() in ("1", "true", "yes"))
    max_remediation_retries: int = field(default_factory=lambda: int(os.getenv("MAX_REMEDIATION_RETRIES", "2")))

    alert_webhook_secret: str | None = field(default_factory=lambda: os.getenv("ALERT_WEBHOOK_SECRET"))
    incident_report_dir: str = field(default_factory=lambda: os.getenv("INCIDENT_REPORT_DIR", "./incident_reports"))


def from_env() -> Settings:
    return Settings()


settings = from_env()


def get_settings() -> Settings:
    return settings
