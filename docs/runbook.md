# SovereignGuard Runbook

## Local run
```
pip install -r requirements.txt
cp .env.example .env  # optional
uvicorn src.main:app --reload
```

## Test
```
pytest -q
```

## Trigger a test alert
```
curl -X POST http://localhost:8000/webhook/alert \
  -H 'Content-Type: application/json' \
  -d '{"alert_id":"t1","service":"payments","metric":"http_5xx","severity":"high","summary":"5xx spike"}'
```

## Environment variables
- `LLM_PROVIDER` = mock | anthropic | bedrock
- `ANTHROPIC_API_KEY` — for anthropic provider
- `DRY_RUN` — true/false (default true)
- `ALERT_WEBHOOK_SECRET` — optional webhook secret
- `INCIDENT_REPORT_DIR` — where reports are written
