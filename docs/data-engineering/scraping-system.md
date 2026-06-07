# Scraping System

!!! success "Phase 1 — Implemented"
    Automated PDF download scripts for all eight target Malaysian Blue-Chip companies are implemented in Phase 1.  
    Powered by **Playwright** with anti-bot stealth patches and idempotent disk-based deduplication.
    Operational triggering is now done via `jobs.weekly_ingestion` and pipeline trigger workflows.

---

## Overview

The FinSight scraper monitors each company's investor-relations (IR) web page, locates quarterly financial statement PDFs, and downloads them to a structured local directory tree. The scraper is fully idempotent — if a PDF already exists on disk it is silently skipped, making re-runs and backfills safe.

The downloaded PDFs feed directly into the ETL pipeline through `src/jobs/weekly_ingestion.py`, which scans the same directory for unprocessed files and loads extracted values into PostgreSQL.

---

## Target Companies

| Company | Ticker | IR Source | Report Types | Coverage |
|---|---|---|---|---|
| Maybank | `MAYBANK` | maybank.com (IR page) | Quarterly Financial Statements | 2020–2025 |
| CIMB | `CIMB` | CIMB IR page | Quarterly Financial Statements | 2020–2025 |
| Tenaga Nasional | `TNB` | TNB IR page | Quarterly Financial Statements | 2021–2025 |
| Petronas | `PETRONAS` | Petronas IR page | Quarterly Financial Statements | 2020–2025 |
| Maxis | `MAXIS` | Maxis IR page | Quarterly Financial Statements | 2021–2025 |
| Telekom Malaysia | `TELEKOM` | TM IR page | Quarterly Financial Statements | 2020–2025 |
| Genting | `GENTING` | Genting IR page | Quarterly Financial Statements | 2020–2025 |
| Sunway | `SUNWAY` | Sunway IR page (ChartNexus iframe) | Quarterly Financial Statements | 2020–2025 |

---

## Technology

### Playwright (Primary)

All scrapers use **Playwright async API** with a real Chromium browser (`channel="chrome"`) running in headless mode. Key configuration:

```python
browser = await p.chromium.launch(
    channel="chrome",
    headless=True,
    args=[
        "--headless=new",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--no-sandbox",
        "--window-size=1920,1080",
    ],
)

context = await browser.new_context(
    viewport={"width": 1920, "height": 1080},
    accept_downloads=True,
    locale="en-US",
    timezone_id="Asia/Kuala_Lumpur",
    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
)
```

### Anti-Bot / WAF Evasion

Several IR portals (notably Maybank) are protected by **Imperva WAF**. The scraper applies a multi-layer evasion strategy:

1. **`playwright-stealth`** — wraps the browser context with `Stealth()` to patch fingerprinting vectors
2. **WebGL renderer spoofing** — overrides `getParameter()` to report Apple M2 GPU strings
3. **Navigator property spoofing** — sets `hardwareConcurrency=8`, `deviceMemory=8`, `platform='MacIntel'`
4. **Human behavioural simulation** — smooth scroll events before interacting with page elements
5. **Link hover before download** — hovers the link before triggering the download to build a behavioural score with Imperva
6. **Session refresh between retries** — re-navigates to the IR page before each retry attempt to refresh the WAF session token (`reese84` cookie)

---

## Scraping Logic

### Detection — Finding the PDF Link

Each company module implements an `async def scrape(page, base_dir, year, quarter)` function with company-specific DOM navigation:

- **Maybank**: Navigates to the IR page, selects the fiscal year from a `<select>` dropdown (`.filter-label`), then finds the link with CSS selector matching `Financial Statements` → target quarter.
- **Sunway**: The IR content lives inside a `#investor-iframe` from ChartNexus. The scraper uses `page.frame_locator()` to enter the iframe and matches links by `href` and `innerText` patterns containing the year and quarter number.
- **Other companies**: Similar DOM traversal patterns adapted to each site's specific structure.

### Download — Fetching the PDF

After resolving the PDF URL, the file is downloaded using `page.context.request.get()` (not Playwright's `download` event), which carries the session cookies and Referer header:

```python
response = await page.context.request.get(
    full_pdf_url,
    headers={"Referer": IR_PAGE_URL},
    timeout=120_000,   # 120 s — large PDFs over Imperva CDN can be slow
)
pdf_bytes = await response.body()
```

**PDF validation:** Before saving, the magic bytes are checked — `pdf_bytes.startswith(b"%PDF")`. If the response is an HTML page (WAF block or redirect), the file is discarded and an error is logged.

**Retry logic (Maybank):** Up to 3 attempts per quarter. On failure the scraper waits 15 seconds and re-navigates to the IR page to refresh Imperva session cookies before retrying. Non-200 HTTP responses and non-PDF content abort immediately (retrying won't help).

### Storage — File Naming and Layout

Files are written to:

```
src/scraper/data/raw/
├── MAYBANK/
│   ├── MAYBANK_2024_Q1.pdf
│   ├── MAYBANK_2024_Q2.pdf
│   └── ...
├── CIMB/
│   └── CIMB_2024_Q1.pdf
├── TNB/
├── PETRONAS/
├── MAXIS/
├── TELEKOM/
├── GENTING/
└── SUNWAY/
```

Filename convention: `{TICKER}_{YEAR}_{QUARTER}.pdf` — this format is parsed by the ETL pipeline's `_extract_metadata_from_path()` to derive `ticker`, `fiscal_year`, and `report_period`.

The base directory is configurable via `FINSIGHT_RAW_DIR` in `.env` (default: `src/scraper/data/raw`).

---

## Scheduling

### Archived scheduler

`src/scraper/scheduler.py` is retained as an archived compatibility stub and is not the
recommended orchestration path.

### Two Operating Modes

| Mode | CLI Flag | Behaviour |
|---|---|---|
| **Full backfill** (default) | `python main.py` | Iterates every `(year, quarter)` in each company's configured range; skips files already on disk |
| **Latest-only** | `python main.py --latest` | Checks only the most recently completed quarter (conservative 45-day lag from quarter-end) |

The deployable ingestion command wraps the scraper and downstream ETL stages:

```bash
PYTHONPATH=src python -m jobs.weekly_ingestion --latest-only
PYTHONPATH=src python -m jobs.weekly_ingestion --skip-scrape --dry-run
```

The `current_quarter()` helper computes the latest safely-released quarter:

```python
def current_quarter() -> tuple[int, str]:
    today = date.today()
    if today.month <= 3:   return today.year - 1, "Q4"
    elif today.month <= 6: return today.year,     "Q1"
    elif today.month <= 9: return today.year,     "Q2"
    else:                  return today.year,     "Q3"
```

### Airflow Integration

The Airflow DAG (`dags/finsight_etl_dag.py`) remains available for deployments that prefer Airflow. It polls `FINSIGHT_RAW_DIR` for new PDFs via `db.loader.get_unprocessed_pdfs()` and processes whatever the scraper or weekly ingestion job has already written.

A separate weekly DAG — **`ml_features_etl`** (`dags/ml_features_etl_dag.py`) —
computes ML training metrics from yfinance, TradingView, Investing.com,
i3investor, and Malaysia Warrants into `predictive_features`.  See
[ML Features ETL](ml-features-etl.md).

For Airflow-based deployments, run the scraper stage and Airflow stack side-by-side:

```
scraper scheduler     →  src/scraper/data/raw/  ←  Airflow ETL DAG
(writes new PDFs)                                  (reads & processes PDFs)
```

---

## Error Handling

| Scenario | Handling |
|---|---|
| WAF block (HTML returned instead of PDF) | Magic-byte validation catches it; error logged; file not saved |
| HTTP non-200 response | Logged; no retry (server-side rejection) |
| Download timeout (>120 s) | Exception caught; retry with session refresh (up to 3 attempts) |
| Link not found for quarter | Warning logged (quarter may not be published yet); silently skipped |
| Year dropdown not found | Error logged (possible full WAF block); function returns `None` |
| Company-level fatal error | Caught at orchestrator level; other companies continue |
| All retries exhausted | Error logged with attempt count; file not saved; next quarter attempted |

All errors are written to `scraper.log` (and echoed to stdout) using Python's standard `logging` module. The log file is created in `src/scraper/`.

---

## Configuration

Per-company settings are defined in `COMPANY_CONFIG` in `src/scraper/main.py`:

```python
COMPANY_CONFIG = [
    {"module": maybank,  "start": 2020, "end": 2025, "quarters": ["Q1", "Q2", "Q3", "Q4"]},
    {"module": sunway,   "start": 2020, "end": 2025, "quarters": ["Q1", "Q2", "Q3", "Q4"]},
    {"module": genting,  "start": 2020, "end": 2025, "quarters": ["Q1", "Q2", "Q3", "Q4"]},
    {"module": telekom,  "start": 2020, "end": 2025, "quarters": ["Q1", "Q2", "Q3", "Q4"]},
    {"module": maxis,    "start": 2021, "end": 2025, "quarters": ["Q1", "Q2", "Q3", "Q4"]},
    {"module": petronas, "start": 2020, "end": 2025, "quarters": ["Q1", "Q2", "Q3", "Q4"]},
    {"module": tnb,      "start": 2021, "end": 2025, "quarters": ["Q1", "Q2", "Q3", "Q4"]},
    {"module": cimb,     "start": 2020, "end": 2025, "quarters": ["Q1", "Q2", "Q3", "Q4"]},
]
```

Relevant environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `FINSIGHT_RAW_DIR` | `src/scraper/data/raw` | Root directory where PDFs are written |

---

## Running the Scraper

```bash
# Navigate to the scraper directory
cd src/scraper

# Install dependencies (if not already done)
pip install playwright playwright-stealth schedule
playwright install chromium

# One-off: download all missing PDFs for all companies
python main.py

# One-off: check only the latest quarter (fast)
python main.py --latest

# Scheduled orchestration is handled externally (for example CI triggers)
# and by invoking jobs.weekly_ingestion in controlled environments.
```
