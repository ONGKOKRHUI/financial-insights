# External Pipeline Trigger Runbook

## Purpose

This runbook documents the production orchestration model for Render deployment:

- No internal Python scheduler loops
- No APScheduler/background cron in app code
- Pipeline runs only when `POST /run-pipeline` is called
- GitHub Actions scheduled workflow is the trigger source

This keeps the backend stateless and restart-safe on Render.

---

## Target Architecture

```text
GitHub Actions (weekly cron)
        ↓
POST /run-pipeline (Render backend)
        ↓
src/jobs/weekly_ingestion.py -> run_pipeline()
        ↓
scrape -> parse -> extract -> load
```

---

## Prerequisites

1. Backend deployed on Render and reachable via HTTPS.
2. Route `POST /run-pipeline` available in backend.
3. `API_SECRET_KEY` configured in Render environment variables.
4. GitHub Actions workflow `.github/workflows/trigger-weekly-pipeline.yml` present.
5. GitHub repository secrets configured:
   - `RENDER_PIPELINE_TRIGGER_URL`
   - `PIPELINE_TRIGGER_API_KEY`

---

## Environment and Secrets

### Render (backend env vars)

Set in Render dashboard:

- `API_SECRET_KEY=<long-random-secret>`

Recommended generation:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### GitHub Actions (repository secrets)

Set in GitHub repository settings -> Secrets and variables -> Actions:

- `RENDER_PIPELINE_TRIGGER_URL=https://<your-render-service>/run-pipeline`
- `PIPELINE_TRIGGER_API_KEY=<same value as Render API_SECRET_KEY>`

---

## Endpoint Contract

### Request

- Method: `POST`
- URL: `/run-pipeline`
- Header: `x-api-key: <API_SECRET_KEY>`
- Body: optional (workflow sends no payload)

### Success response

- Status: `200 OK`
- JSON:

```json
{ "status": "success" }
```

### Error responses

- `403 Forbidden`: API key missing/invalid
- `409 Conflict`: pipeline already running (overlap prevention lock)
- `500 Internal Server Error`: `API_SECRET_KEY` not configured on server

---

## GitHub Actions Schedule

Workflow: `.github/workflows/trigger-weekly-pipeline.yml`

- Cron: `0 1 * * 1` (Monday 01:00 UTC, Monday 09:00 MYT)
- Also supports manual trigger via `workflow_dispatch`

---

## Manual Verification (Before Enabling Cron)

### 1) Health check backend

```bash
curl --fail --show-error --silent https://<your-render-service>/health
```

Expected:

```json
{"status":"ok"}
```

### 2) Trigger pipeline with valid key

```bash
curl --fail --show-error --silent \
  -X POST "https://<your-render-service>/run-pipeline" \
  -H "x-api-key: <API_SECRET_KEY>" \
  -H "Content-Type: application/json"
```

Expected:

```json
{"status":"success"}
```

### 3) Validate unauthorized case

```bash
curl --include --silent \
  -X POST "https://<your-render-service>/run-pipeline" \
  -H "x-api-key: wrong-key"
```

Expected HTTP status: `403`

### 4) Validate overlap protection

Trigger one run, then quickly trigger again while first run is still active.

Expected second response HTTP status: `409`

---

## Operational Logging Expectations

`run_pipeline()` writes lifecycle logs with:

- pipeline start timestamp
- pipeline end timestamp
- duration seconds
- success/failure summary

Use Render logs to verify:

1. trigger request received
2. ingestion run started
3. completion line with duration and success/error counts

---

## Idempotency and Safety Notes

- In-memory overlap lock prevents concurrent runs in the same app instance.
- Existing DB idempotency (`pipeline_runs` tracking + UPSERTs) remains unchanged.
- If Render restarts between runs, system remains safe because execution is externally triggered and stateless.

---

## Local Development Behavior (Unchanged)

Keep local Airflow orchestration for Docker development:

- `docker-compose.airflow.yml`
- `dags/finsight_etl_dag.py`

Cloud scheduling and local Airflow are intentionally separate concerns.

---

## Troubleshooting

### 403 Unauthorized

Check:

- `x-api-key` header is present in request
- value matches Render `API_SECRET_KEY` exactly
- no extra spaces/newlines in GitHub secret value

### 409 Pipeline already running

Meaning:

- a prior run is still in progress

Action:

- wait for current run to complete
- do not add retry loops with very short intervals

### 500 API_SECRET_KEY not configured

Check:

- Render environment variable exists
- service redeployed after setting env var

### GitHub Action fails with network/HTTP errors

Check:

- `RENDER_PIPELINE_TRIGGER_URL` points to correct service and path
- Render service is up and responding on `/health`
- workflow secret names match exactly

---

## Rollback Plan

If trigger architecture needs temporary rollback:

1. Disable schedule in GitHub Actions workflow.
2. Keep endpoint deployed (no data model rollback needed).
3. Investigate root cause using Render logs and recent workflow runs.

Do not reintroduce internal scheduler loops in backend code.
