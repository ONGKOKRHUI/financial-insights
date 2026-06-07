# ML Features ETL Pipeline

!!! success "Implemented"
    The five-phase ML feature pipeline computes **21 predictive metrics** per
    `(ticker, fiscal_year, fiscal_quarter)` and stores them in the
    `predictive_features` PostgreSQL table. Orchestrated weekly by the
    **`ml_features_etl`** Airflow DAG.

!!! info "Metrics 19–20 (schema only)"
    `guidance_beat_indicator` and `backlog_order_book_yoy_growth_pct` exist in
    the database schema but are **not yet populated** by the pipeline. Phase 5
    currently computes **metric 21 only** (`sector_peer_earnings_sentiment`).

---

## Overview

This pipeline complements the existing PDF → LLM → PostgreSQL ETL
(`finsight_etl`). Where the financial ETL extracts structured statement values
from quarterly report PDFs, the ML features pipeline **fetches external market
data, earnings estimates, KLSE shareholding trades, and sector peer signals** to
produce a flat feature row suitable for machine learning model training.

```
Weekly Airflow (ml_features_etl)
────────────────────────────────────────────────────────────────────────────
discover_feature_targets
  → run_feature_pipeline (5 phases per ticker, shared PipelineContext cache)
    → load_feature_payloads
      → PostgreSQL predictive_features
```

Each target runs phases in this order inside `ml_pipeline_runner.run_for_target`:

1. Phase 1 — fundamentals (yfinance)
2. Phase 2 — valuation (yfinance + TradingView sector peers)
3. Phase 3 — earning surprises for sector peers discovered in Phase 2 (cached)
4. Phase 3 — earning surprises for the target ticker
5. Phase 4 — money flow (i3investor + Malaysia Warrants)
6. Phase 5 — sector peer earnings sentiment (metric 21)

Individual phase failures are logged and recorded in `source_metadata`; they do
not abort the full run for other tickers or phases.

---

## Pipeline diagram

```mermaid
flowchart TD
    subgraph orchestration [Orchestration]
        T1[discover_feature_targets]
        T2[run_feature_pipeline]
        T3[load_feature_payloads]
        T1 --> T2 --> T3
    end

    subgraph phases [Five phases per ticker]
        P1[Phase 1 Fundamentals\nyfinance + i3investor margins]
        P2[Phase 2 Valuation\nyfinance + TradingView peers]
        P3[Phase 3 Earning Surprises\nInvesting.com → yfinance → i3investor]
        P4[Phase 4 Money Flow\ni3investor + Malaysia Warrants IV]
        P5[Phase 5 Forward-Looking\nsector peer sentiment only]
        P1 --> P2 --> P3 --> P4 --> P5
    end

    T2 --> P1
    P5 --> DB[(predictive_features)]
    T3 --> DB
```

---

## The 21 metrics

One row per `(ticker, fiscal_year, fiscal_quarter)`. Columns are grouped by
source phase. **Populated** columns are filled by the current pipeline;
**planned** columns are reserved in the schema for future PDF-based extraction.

### Phase 3 — Earning surprises (metrics 1–5)

| Column | Description | Status |
|--------|-------------|--------|
| `revenue_beat_rate_8q` | Fraction of last 8 quarters with revenue beat | Populated |
| `eps_beat_rate_8q` | Fraction of last 8 quarters with EPS beat | Populated |
| `avg_revenue_surprise_pct` | Mean revenue surprise % vs consensus | Populated |
| `avg_eps_surprise_pct` | Mean EPS surprise % vs consensus | Populated |
| `consecutive_double_beat_quarters` | Consecutive most-recent quarters beating both revenue and EPS | Populated |

### Phase 4 — Money flow (metrics 6–9)

| Column | Description | Status |
|--------|-------------|--------|
| `net_institutional_cash_flow_myr` | Net substantial-shareholder buying from i3investor Form 29B tables (MYR, 90-day lookback) | Populated |
| `institutional_flow_to_market_cap_ratio` | Institutional flow / market cap | Populated |
| `net_insider_trading_value_myr` | Net director trading from i3investor Form 29C tables (MYR, 90-day lookback) | Populated |
| `options_iv_rank_pct` | Implied volatility of the most liquid warrant (Malaysia Warrants screener JSON) | Populated |

### Phase 1 — Fundamentals (metrics 10–14)

| Column | Description | Status |
|--------|-------------|--------|
| `revenue_yoy_growth_pct` | Revenue Q_n vs Q_{n-4} YoY (%) | Populated |
| `net_income_yoy_growth_pct` | Net income Q_n vs Q_{n-4} YoY (%) | Populated |
| `gross_margin_delta_qoq_pct` | Gross margin change QoQ (pp); i3investor PBT/Revenue fallback for banks | Populated |
| `operating_margin_delta_qoq_pct` | Operating margin change QoQ (pp); i3investor NP/Revenue fallback for banks | Populated |
| `fcf_yield_pct` | FCF TTM / market cap (%) | Populated |

### Phase 2 — Valuation (metrics 15–18)

| Column | Description | Status |
|--------|-------------|--------|
| `forward_pe_peer_zscore` | Trailing PE z-score vs dynamically discovered sector peers | Populated |
| `forward_pe_peer_discount_pct` | % discount of trailing PE vs sector mean | Populated |
| `forward_ps_ratio` | Market cap / TTM revenue | Populated |
| `peg_ratio` | yfinance `pegRatio` | Populated |

!!! note "Trailing PE for peer comparison"
    TradingView does not expose forward PE for most KLSE listings. Phase 2 uses
    **trailing PE** (`price_earnings_ttm`) consistently for both the target and
    sector peers. `source_metadata.phase_2_pe_type` records `"trailing/TTM"`.

### Phase 5 — Forward-looking (metrics 19–21)

| Column | Description | Status |
|--------|-------------|--------|
| `guidance_beat_indicator` | Boolean: internal KPI/guidance achieved | Planned |
| `backlog_order_book_yoy_growth_pct` | Order book / backlog YoY growth (%) | Planned |
| `sector_peer_earnings_sentiment` | Average revenue beat rate of TradingView sector peers (0–1) | Populated |

Metric 21 is computed from `peer_beat_rates` populated by the runner after
Phase 2 peer discovery and cached Phase 3 fetches — no PDF parsing is required.

---

## Source modules

| File | Role |
|------|------|
| `src/scraper/ml_pipeline_runner.py` | CLI entry point, `PipelineContext` cache, orchestrator |
| `src/scraper/ml_features/types.py` | `FeatureTarget`, `FeaturePayload`, `PeerRef`, KLSE code maps |
| `src/scraper/ml_features/phase_1_fundamentals.py` | yfinance quarterly statements; i3investor margin fallback |
| `src/scraper/ml_features/phase_2_valuation.py` | yfinance + TradingView Malaysia screener peer discovery |
| `src/scraper/ml_features/phase_3_surprises.py` | Earnings surprise metrics with multi-source fallback chain |
| `src/scraper/ml_features/investing_com.py` | Investing.com JSON API + Scrapling page fallback |
| `src/scraper/ml_features/i3investor.py` | KLSE HTML scrapers (margins, trades, earnings fallback) |
| `src/scraper/ml_features/phase_4_money_flow.py` | i3investor shareholding trades + warrant IV |
| `src/scraper/ml_features/phase_5_forward_looking.py` | Sector peer earnings sentiment (metric 21) |
| `src/scraper/ml_features/scrapling_utils.py` | Shared Scrapling browser helpers (Investing.com fallback) |
| `src/db/loader.py` | `upsert_predictive_features`, batch loader, idempotent DDL |
| `dags/ml_features_etl_dag.py` | Weekly Airflow orchestration |
| `src/backend/models.py` | `PredictiveFeature` ORM model |
| `src/backend/alembic/versions/002_add_predictive_features.py` | Schema migration |

---

## Data sources

| Phase | Primary source | Fallback chain |
|-------|----------------|----------------|
| 1 | [yfinance](https://pypi.org/project/yfinance/) (`1155.KL` Bursa numeric codes) | i3investor `/web/stock/financial-quarter/{code}` for bank margin QoQ |
| 2 | yfinance (market cap, P/S, PEG) + [TradingView Malaysia screener](https://scanner.tradingview.com/malaysia/scan) | — |
| 3 | [Investing.com](https://www.investing.com/) earnings JSON API (~350 ms) | Scrapling page load → yfinance `earnings_history` (EPS only) → i3investor analyst earnings |
| 4 | [i3investor](https://klse.i3investor.com/) Form 29B/29C HTML trade tables | — |
| 4 (IV) | [Malaysia Warrants](https://www.malaysiawarrants.com.my/) `ScreenerJSONServlet` | — |
| 5 | Phase 2 peer list + Phase 3 cached beat rates | — |

### Cross-target caching

`PipelineContext` in `ml_pipeline_runner.py` ensures:

- Each `(ticker, fiscal_year, fiscal_quarter)` is fetched at most once for Phase 3
- Sector peers discovered by TradingView in Phase 2 reuse the same Phase 3 cache
- Multiple targets in the same sector share one peer beat-rate list for metric 21

### yfinance symbol mapping

Pipeline tickers (e.g. `MAYBANK`) map to Bursa numeric codes (e.g. `1155.KL`)
via `_KLSE_YFINANCE_CODES` in `types.py`. Name-based symbols like `MAYBANK.KL`
return empty data from yfinance.

---

## Running locally

### Install dependencies

```bash
pip install -r src/scraper/requirements.txt
```

Scrapling (used only when the Investing.com JSON API fallback path runs) may
require a Chromium install. Most runs succeed via the fast JSON API without a
browser.

Optional Scrapling / patchright setup:

```bash
playwright install chrome
```

### Single run (writes to DB)

```bash
cd src/scraper
python ml_pipeline_runner.py \
  --tickers MAYBANK,CIMB,MAXIS \
  --fiscal-year 2025 \
  --fiscal-quarter Q4
```

Default tickers when `--tickers` is omitted:
`MAYBANK,CIMB,SUNWAY,GENTING,TELEKOM,MAXIS,TNB`.

### Dry run (inspect payloads, no DB writes)

```bash
python ml_pipeline_runner.py --tickers MAYBANK --dry-run
```

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/finsight` | Loader connection |
| `ML_FEATURE_TICKERS` | 7 default KLSE tickers (see above) | Comma-separated override |
| `ML_FEATURE_YEAR` | `2025` | Fiscal year |
| `ML_FEATURE_QUARTER` | `Q4` | Fiscal quarter |
| `ML_FEATURE_LIMIT` | `0` (unlimited) | Airflow ticker cap |
| `INVESTING_SOLVE_CLOUDFLARE` | `false` | Scrapling CF solver for Investing.com fallback |
| `SCRAPLING_REAL_CHROME` | `false` | Use system Chrome instead of bundled Chromium |

Apply the schema before the first DB write:

```bash
cd src/backend && alembic upgrade head
```

---

## Airflow orchestration

| Property | Value |
|----------|-------|
| DAG ID | `ml_features_etl` |
| Schedule | `0 1 * * MON` (Monday 09:00 MYT) |
| Retries | 3 × 5-minute delay |

**Task graph:**

```
discover_feature_targets >> run_feature_pipeline >> load_feature_payloads
```

| Task | What it does |
|------|--------------|
| `discover_feature_targets` | Builds target list from env vars; auto-selects latest completed quarter when year/quarter unset; pushes via XCom |
| `run_feature_pipeline` | Runs all five phases with `persist=False`; pushes payloads via XCom |
| `load_feature_payloads` | Calls `upsert_predictive_feature_batch`; runs `ensure_predictive_features_table()` on first load |

Trigger manually:

```bash
docker compose -f docker-compose.airflow.yml exec -T airflow-webserver \
  airflow dags trigger ml_features_etl
```

Smoke test (no scheduler):

```bash
docker compose -f docker-compose.airflow.yml exec -T airflow-webserver \
  airflow dags test ml_features_etl 2025-01-06
```

Cap tickers for a fast validation run:

```bash
ML_FEATURE_LIMIT=2 ML_FEATURE_TICKERS=MAYBANK,CIMB,TNB \
  docker compose -f docker-compose.airflow.yml exec -T airflow-webserver \
  airflow dags test ml_features_etl 2025-01-06
```

---

## Database persistence

Rows are upserted into `predictive_features` with a unique constraint on
`(ticker, fiscal_year, fiscal_quarter)`.

**Partial-run safety:** metric columns use `COALESCE` on conflict — a phase
that returns `NULL` for a metric does not overwrite a previously stored value.

Apply the schema via Alembic:

```bash
cd src/backend
alembic upgrade head
```

See [Database Schema](../backend/database-schema.md#predictive_features) for the
full column reference.

---

## Querying for model training

Export feature matrix:

```sql
SELECT pf.*, c.sector, c.industry
FROM predictive_features pf
JOIN companies c ON c.ticker = pf.ticker
WHERE pf.fiscal_year >= 2023
ORDER BY pf.ticker, pf.fiscal_year, pf.fiscal_quarter;
```

Check coverage per ticker:

```sql
SELECT ticker,
       COUNT(*) AS quarters,
       COUNT(revenue_yoy_growth_pct) AS fundamentals_ok,
       COUNT(revenue_beat_rate_8q) AS surprises_ok,
       COUNT(sector_peer_earnings_sentiment) AS sentiment_ok,
       COUNT(guidance_beat_indicator) AS guidance_ok
FROM predictive_features
GROUP BY ticker
ORDER BY ticker;
```

Inspect provenance for a single row:

```sql
SELECT ticker, fiscal_year, fiscal_quarter, source_metadata
FROM predictive_features
WHERE ticker = 'MAYBANK'
ORDER BY fiscal_year DESC, fiscal_quarter DESC
LIMIT 1;
```

---

## Tests

```bash
# Types, yfinance symbol maps, discover_targets, PipelineContext
pytest tests/test_ml_features_types.py -v

# ORM registration + loader UPSERT mocks
pytest src/backend/tests/test_predictive_features.py -v

# Investing.com earnings parser (offline fixtures)
pytest tests/test_investing_com_parser.py -v

# i3investor HTML parsers (offline fixtures)
pytest tests/test_i3investor_scrapers.py -v

# Phase 5 sector peer sentiment
pytest tests/test_phase_5_bursa_pdf.py -v
```

---

## Related documentation

- [ETL Pipeline](etl-pipeline.md) — PDF → LLM financial statement ETL
- [Scraping System](scraping-system.md) — PDF acquisition (separate from ML features)
- [Database Schema](../backend/database-schema.md) — `predictive_features` table
- [Model Training](../mlops/model-training.md) — how features feed Phase 6 ML
