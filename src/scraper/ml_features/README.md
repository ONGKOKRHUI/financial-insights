# ML Features Pipeline

This pipeline retrieves predictive ML features for Bursa Malaysia tickers and
returns one feature row per `(ticker, fiscal_year, fiscal_quarter)`.

It is orchestrated by `src/scraper/ml_pipeline_runner.py` and computes metrics
from yfinance, TradingView sector peers, Investing.com earnings, i3investor, and
Malaysia Warrants.

## Quick Start

Run from the repository root:

```bash
python src/scraper/ml_pipeline_runner.py \
  --tickers TNB \
  --fiscal-year 2025 \
  --fiscal-quarter Q4 \
  --dry-run
```

`--dry-run` prints the generated JSON payload to stdout and does not write to
PostgreSQL.

Example one-liner:

```bash
python src/scraper/ml_pipeline_runner.py --tickers TNB --fiscal-year 2025 --fiscal-quarter Q4 --dry-run
```

## Retrieve Multiple Tickers

Pass a comma-separated ticker list:

```bash
python src/scraper/ml_pipeline_runner.py \
  --tickers MAYBANK,CIMB,TNB \
  --fiscal-year 2025 \
  --fiscal-quarter Q4 \
  --dry-run
```

If `--tickers` is omitted, the runner uses the default tickers in
`ml_pipeline_runner.py`:

```text
MAYBANK,CIMB,SUNWAY,GENTING,TELEKOM,MAXIS,TNB
```

## Persist to Database

Remove `--dry-run` to UPSERT into `predictive_features`:

```bash
python src/scraper/ml_pipeline_runner.py \
  --tickers TNB \
  --fiscal-year 2025 \
  --fiscal-quarter Q4
```

Required for DB writes:

```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/finsight"
```

Apply the schema first if needed:

```bash
cd src/backend
alembic upgrade head
cd ../..
```

## Query Retrieved Data

After a persisted run, query the feature row:

```sql
SELECT
    ticker,
    fiscal_year,
    fiscal_quarter,
    revenue_beat_rate_8q,
    eps_beat_rate_8q,
    sector_peer_earnings_sentiment,
    source_metadata
FROM predictive_features
WHERE ticker = 'TNB'
  AND fiscal_year = 2025
  AND fiscal_quarter = 'Q4';
```

With `psql`:

```bash
psql "$DATABASE_URL" -c "
SELECT ticker,
       fiscal_year,
       fiscal_quarter,
       revenue_beat_rate_8q,
       eps_beat_rate_8q,
       sector_peer_earnings_sentiment
FROM predictive_features
WHERE ticker = 'TNB'
  AND fiscal_year = 2025
  AND fiscal_quarter = 'Q4';
"
```

## Output Shape

The dry-run command returns a JSON array. Each object is ready for the
`predictive_features` loader and includes:

- Ticker and fiscal period keys.
- Phase 1 fundamentals, such as revenue growth and margin deltas.
- Phase 2 valuation metrics, such as peer PE z-score and PEG.
- Phase 3 earnings surprise metrics, such as revenue and EPS beat rates.
- Phase 4 money flow metrics, such as institutional cash flow.
- Phase 5 `sector_peer_earnings_sentiment`.
- `source_metadata`, a JSON string containing source and provenance details.

## Useful Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | local `finsight` DB | PostgreSQL connection for persisted runs |
| `ML_FEATURE_TICKERS` | default ticker list | Comma-separated ticker override |
| `ML_FEATURE_YEAR` | `2025` | Fiscal year override |
| `ML_FEATURE_QUARTER` | `Q4` | Fiscal quarter override |
| `ML_PEER_SENTIMENT_SAMPLE_LIMIT` | `10` | Max usable peer rates for sector sentiment |
| `ML_PEER_SENTIMENT_MIN_RATES` | `1` | Minimum rates before bounded slow fallback |
| `ML_PEER_SENTIMENT_FALLBACK_LIMIT` | `2` | Max slow peer fallback fetches when undersampled |
| `INVESTING_BEARER_TOKEN` | unset | Optional Investing.com token to skip browser bootstrap |

## Notes

- Sector peer sentiment uses TradingView peers and the fast Investing.com API
  first. It uses revenue beat rate when available and EPS beat rate as fallback.
- Known Investing.com instrument IDs live in `types.py` to avoid repeated slow
  discovery.
- Full Scrapling fallback is kept for target tickers, but peer fallbacks are
  bounded to keep single-company runs fast.

