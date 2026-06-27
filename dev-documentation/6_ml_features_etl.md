# ML Features ETL — Integration Notes

**Status:** Implemented (19 of 21 metrics populated; metrics 19–20 reserved)  
**Source pipeline:** [eychoong/malaysia_stock](https://github.com/eychoong/malaysia_stock)  
**Target repo:** `financial-insights`

This document describes the five-phase ML feature ingestion pipeline that computes predictive metrics per `(ticker, fiscal_year, fiscal_quarter)` and stores them in the `predictive_features` PostgreSQL table for downstream model training.

Public MkDocs page: `docs/data-engineering/ml-features-etl.md`.

---

## Key files

| Area | Path |
|------|------|
| ORM model | `src/backend/models.py` → `PredictiveFeature` |
| Alembic migration | `src/backend/alembic/versions/002_add_predictive_features.py` |
| DB UPSERT loader | `src/db/loader.py` → `upsert_predictive_features`, `upsert_predictive_feature_batch`, `ensure_predictive_features_table` |
| Pipeline runner | `src/scraper/ml_pipeline_runner.py` → `run_pipeline`, `PipelineContext` |
| Phase modules | `src/scraper/ml_features/phase_1_fundamentals.py` … `phase_5_forward_looking.py` |
| External scrapers | `src/scraper/ml_features/investing_com.py`, `i3investor.py`, `scrapling_utils.py` |
| Shared types | `src/scraper/ml_features/types.py` |
| Airflow DAG | `dags/ml_features_etl_dag.py` |
| Scraper deps | `src/scraper/requirements.txt` |
| Backend tests | `src/backend/tests/test_predictive_features.py` |
| Parser / type tests | `tests/test_ml_features_types.py`, `test_investing_com_parser.py`, `test_i3investor_scrapers.py`, `test_phase_5_bursa_pdf.py` |
| Public docs | `docs/data-engineering/ml-features-etl.md` |

---

## Data flow

```
Airflow ml_features_etl (weekly)
  discover_feature_targets
    → run_feature_pipeline (5 phases, persist=False, shared PipelineContext)
      → load_feature_payloads (upsert_predictive_feature_batch)
        → PostgreSQL predictive_features
```

Manual / local run:

```bash
cd src/scraper
python ml_pipeline_runner.py --tickers MAYBANK,CIMB --fiscal-year 2025 --fiscal-quarter Q4
python ml_pipeline_runner.py --dry-run   # no DB writes
```

Runner phase order per target (`run_for_target`):

1. Phase 1 fundamentals  
2. Phase 2 valuation (+ TradingView sector peer discovery)  
3. Phase 3 surprises for sector peers (fast peer mode, cached in `PipelineContext`)  
4. Phase 3 surprises for the target ticker  
5. Phase 4 money flow  
6. Phase 5 sector peer sentiment (metric 21 only)

---

## Five phases and 21 metrics

| Phase | Module | Primary sources | Metrics | Populated? |
|-------|--------|-----------------|---------|------------|
| 1 | `phase_1_fundamentals.py` | yfinance (`1155.KL` codes) + i3investor financial-quarter for bank margins | 10–14 | Yes |
| 2 | `phase_2_valuation.py` | yfinance + TradingView Malaysia screener (trailing PE peers) | 15–18 | Yes |
| 3 | `phase_3_surprises.py` | Investing.com JSON API → Scrapling page → yfinance → i3investor | 1–5 | Yes |
| 4 | `phase_4_money_flow.py` | i3investor Form 29B/29C HTML + Malaysia Warrants IV JSON | 6–9 | Yes |
| 5 | `phase_5_forward_looking.py` | Phase 2 peers + Phase 3 cached beat rates (revenue beat, EPS fallback) | 19–21 | **21 only** |

Metrics **19** (`guidance_beat_indicator`) and **20** (`backlog_order_book_yoy_growth_pct`) exist in the ORM/migration but have **no phase implementation yet**. They were originally planned for local quarterly PDF regex extraction.

Each phase exposes `run(target: FeatureTarget, payload: FeaturePayload) -> None` and only writes its own metric keys into the shared payload.

### Phase 3 fallback chain

1. **Investing.com** — fast JSON API at `endpoints.investing.com/earnings/v1/…`; static instrument IDs in `types._INVESTING_INSTRUMENT_IDS` skip the search round-trip for known tickers  
2. **Scrapling** — full Investing.com page fallback parses `__NEXT_DATA__` and caches any discovered `instrument_id` for the current process  
3. **yfinance** — `earnings_history` (EPS only; revenue metrics stay NULL)  
4. **i3investor** — `analyst-earnings.ajax.php` HTML table  

The runner can disable the slow fallback chain for peer-only requests. Target tickers still use the full fallback chain so their own Phase 3 metrics remain as complete as possible.

### Phase 2 peer discovery

TradingView screener returns liquid KLSE peers (market cap > 1 B MYR, trailing PE in (0, 100]) in the target's sector. Peer refs are stored in `source_metadata.phase_2_peer_refs` and reused by the runner for Phase 3 + metric 21.

### Cross-target cache (`PipelineContext`)

- `get_surprise_payload()` — at most one Phase 3 network fetch per `(ticker, year, quarter, fallback_mode)`  
- `peer_beat_rates()` — cached by `(sector, year, quarter)` for metric 21
- Investing.com bearer-token bootstrap failures are cached briefly (`INVESTING_BEARER_RETRY_SECONDS`) so one local browser failure does not retry for every peer

### Metric 21 peer sentiment

`sector_peer_earnings_sentiment` is computed from the TradingView sector peers discovered in Phase 2. The runner fetches peer Phase 3 data in a fast mode first:

1. Resolve known/static Investing.com instrument IDs, or use the search API when needed.
2. Call the Investing.com earnings JSON API.
3. Skip Scrapling/yfinance/i3investor for the first peer pass to avoid 90-second browser fallbacks.
4. Use `revenue_beat_rate_8q` when available; if the API has no revenue forecast data for that peer, use `eps_beat_rate_8q`.
5. Stop once `ML_PEER_SENTIMENT_SAMPLE_LIMIT` usable rates are collected.

If the fast pass produces fewer than `ML_PEER_SENTIMENT_MIN_RATES`, the runner may try a bounded number of full fallback peer fetches (`ML_PEER_SENTIMENT_FALLBACK_LIMIT`). This protects small sectors from returning `NULL` while preventing a single company run from scraping dozens of slow peer pages.

---

## Database schema

Table: **`predictive_features`**

- Primary key: `id`
- Unique constraint: `(ticker, fiscal_year, fiscal_quarter)` — name `uq_predictive_features_ticker_period`
- FK: `ticker` → `companies.ticker`
- Audit: `source_metadata` (JSON text), `created_at`, `updated_at`

Apply migration:

```bash
cd src/backend
alembic upgrade head
```

For local Airflow before Alembic runs, `ensure_predictive_features_table()` in `loader.py` creates the table idempotently via raw DDL.

---

## UPSERT behaviour

`upsert_predictive_features()` uses PostgreSQL `ON CONFLICT … DO UPDATE` with **`COALESCE(EXCLUDED.col, predictive_features.col)`** on all 21 metric columns. Partial phase failures therefore do not erase previously stored values. `source_metadata` and `updated_at` always update on conflict.

---

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | Yes | PostgreSQL connection for loader |
| `ML_FEATURE_TICKERS` | No | Comma-separated tickers (default: 7 KLSE names) |
| `ML_FEATURE_YEAR` | No | Fiscal year override |
| `ML_FEATURE_QUARTER` | No | Fiscal quarter override (`Q1`–`Q4`) |
| `ML_FEATURE_LIMIT` | No | Cap tickers per Airflow run |
| `ML_PEER_SENTIMENT_SAMPLE_LIMIT` | No | Max usable peer rates for metric 21 (default `10`; non-positive means no cap) |
| `ML_PEER_SENTIMENT_MIN_RATES` | No | Minimum peer rates before bounded full fallback is attempted (default `1`; non-positive means no minimum) |
| `ML_PEER_SENTIMENT_FALLBACK_LIMIT` | No | Max slow full-fallback peer fetches when fast pass is undersampled (default `2`; non-positive means no cap) |
| `INVESTING_BEARER_TOKEN` | No | Pre-supplied Investing.com guest bearer token to skip browser bootstrap |
| `INVESTING_BEARER_RETRY_SECONDS` | No | Cooldown after bearer bootstrap failure (default `300`) |
| `INVESTING_SOLVE_CLOUDFLARE` | No | Scrapling CF solver for Investing.com fallback (default `false`) |
| `SCRAPLING_REAL_CHROME` | No | Use system Chrome for Scrapling (optional) |

**Not required:** `FMP_API_KEY` — the pipeline no longer calls Financial Modeling Prep. Phase 2 uses TradingView; Phase 3 uses Investing.com / yfinance / i3investor.

Default tickers: `MAYBANK,CIMB,SUNWAY,GENTING,TELEKOM,MAXIS,TNB`.

---

## Airflow DAG

| Property | Value |
|----------|-------|
| DAG ID | `ml_features_etl` |
| Schedule | `0 1 * * MON` (09:00 MYT) |
| Tasks | `discover_feature_targets` → `run_feature_pipeline` → `load_feature_payloads` |

When `ML_FEATURE_YEAR` / `ML_FEATURE_QUARTER` are unset, `discover_feature_targets` uses the same 45-day lag logic as the PDF scraper to pick the latest completed quarter.

Local smoke test:

```bash
docker compose -f docker-compose.airflow.yml exec -T airflow-webserver \
  airflow dags test ml_features_etl 2025-01-06
```

Fast validation (2 tickers):

```bash
ML_FEATURE_LIMIT=2 docker compose -f docker-compose.airflow.yml exec -T airflow-webserver \
  airflow dags test ml_features_etl 2025-01-06
```

---

## Relationship to existing ETL

| Pipeline | Purpose | Output table(s) |
|----------|---------|-----------------|
| `finsight_etl` | PDF → LLM extraction | `income_statements`, `kpi_summaries`, etc. |
| `ml_features_etl` | External APIs + KLSE scrapers → computed metrics | `predictive_features` |

The ML pipeline is **independent** of local PDF files today. Metrics 19–20 may later read from `src/scraper/data/raw/` once PDF-based extraction is implemented.

---

## Tests

```bash
pytest tests/test_ml_features_types.py -v
pytest tests/test_investing_com_parser.py -v
pytest tests/test_i3investor_scrapers.py -v
pytest tests/test_phase_5_bursa_pdf.py -v
pytest src/backend/tests/test_predictive_features.py -v
```

---

## Querying for ML training

Example SQL for a training export:

```sql
SELECT
    ticker,
    fiscal_year,
    fiscal_quarter,
    revenue_beat_rate_8q,
    eps_beat_rate_8q,
    revenue_yoy_growth_pct,
    forward_pe_peer_zscore,
    sector_peer_earnings_sentiment
FROM predictive_features
WHERE fiscal_year >= 2023
ORDER BY ticker, fiscal_year, fiscal_quarter;
```

Join to `companies` for sector/industry features:

```sql
SELECT pf.*, c.sector, c.industry, c.market_cap_bln
FROM predictive_features pf
JOIN companies c ON c.ticker = pf.ticker;
```

Check which metrics are populated:

```sql
SELECT ticker,
       COUNT(revenue_beat_rate_8q) AS phase3_ok,
       COUNT(forward_pe_peer_zscore) AS phase2_ok,
       COUNT(sector_peer_earnings_sentiment) AS phase5_ok,
       COUNT(guidance_beat_indicator) AS guidance_planned
FROM predictive_features
GROUP BY ticker;
```
