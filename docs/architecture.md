# SovereignGuard Architecture

## Flow

1. Prometheus/Grafana/CloudWatch detects anomaly (latency, CPU, memory, 5xx).
2. Alert webhook fires to Ops Bot `POST /webhook/alert`.
3. Ops Bot collects logs, stack traces, metrics via log collector.
4. Logs + alert sent to LLM with structured prompt.
5. LLM returns root cause, remediation action, incident report draft.
6. Remediator executes safe action (restart container/service, flush cache, scale out).
7. Standardized incident report generated and persisted.

## Components

- `src/main.py` — FastAPI webhook receiver
- `src/ai_analyzer.py` — LLM integration & prompt templates
- `src/remediator.py` — automated remediation execution
- `src/log_collector.py` — observability data collection
- `src/incident_report.py` — incident report generation
- `infrastructure/` — Terraform IaC for AWS multi-tier architecture
- `observability/` — Prometheus rules & Grafana dashboards
- `ansible/` — remediation playbooks
