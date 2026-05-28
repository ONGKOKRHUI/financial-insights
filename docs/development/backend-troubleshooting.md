# Backend Troubleshooting (Vercel + Render + Supabase)

## Symptom: `/api/financials/CIMB` returns 404

The Vercel BFF route proxies to Render. A **404 from Vercel** used to mean "data not found" even when Render was down. After the proxy fix, check the **response body and status** in DevTools.

## Step 1 — Test Render directly (bypass Vercel)

```bash
curl -i https://finsight-api.onrender.com/health
curl -i https://finsight-api.onrender.com/health/db
curl -i https://finsight-api.onrender.com/financials/CIMB/income-statement
```

| Result | Meaning |
|--------|---------|
| `503` + `x-render-routing: suspend-by-user` | Render service is **suspended**. Open [Render Dashboard](https://dashboard.render.com) → `finsight-api` → **Resume** or fix billing/plan. |
| `/health` OK but `/health/db` 503 | FastAPI is up; **Supabase** connection is wrong or DB is unreachable. Check Render env `DATABASE_URL`. |
| `/health/db` OK, financials 404 | DB is up but **no rows** for CIMB. Run pipeline or enable mock seed (below). |

## Step 2 — Test Vercel BFF (after Render is healthy)

```bash
curl -i https://finsights-mauve.vercel.app/api/financials/CIMB
```

Status should match the backend (e.g. real 404 with FastAPI `detail`, or 200 with JSON data).

## Step 3 — Verify Supabase data (SQL Editor)

```sql
SELECT ticker, name FROM companies WHERE ticker = 'CIMB';
SELECT ticker, fiscal_year FROM income_statements WHERE ticker = 'CIMB' ORDER BY fiscal_year;
```

If `companies` has CIMB but `income_statements` is empty, the API returns 404 by design.

## Step 4 — Empty database on first deploy

Demo data is **not** seeded unless you set on Render:

```env
FINSIGHT_ENABLE_MOCK_SEED=true
```

Restart the service once after setting it (only seeds when `companies` table is empty).

## Environment checklist

| Where | Variable | Purpose |
|-------|----------|---------|
| Render | `DATABASE_URL` | Supabase pooled URI (`postgresql://...`) |
| Render | `ALLOWED_ORIGINS` | Include `https://finsights-mauve.vercel.app` |
| Vercel | `INTERNAL_API_URL` | `https://finsight-api.onrender.com` |
| Vercel | `NEXT_PUBLIC_API_URL` | Same as above for client-side calls |
