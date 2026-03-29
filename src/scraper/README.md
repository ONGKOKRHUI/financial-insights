# FinSight API Scraper

An automated scraper that downloads quarterly financial report PDFs from eight Malaysian public-listed companies and Petronas. Built with Playwright and stealth modules to handle bot-detection measures reliably.

---

## Supported Companies & Coverage

| Company | Ticker | Coverage | Notes |
|---------|--------|----------|-------|
| Maybank | MAY | 2020 – 2025 | Q1–Q4 |
| CIMB Group | CIMB | 2020 – 2025 | Q1–Q4 |
| Sunway | SWB | 2020 – 2025 | Q1–Q4 |
| Genting | GENT | 2020 – 2025 | Q1–Q4 |
| Telekom Malaysia (TM) | T | 2020 – 2025 | Q1–Q4 |
| Petronas | — | 2020 – 2025 | Q1, Q2/1H, Q4/2H only (no Q3) |
| Maxis | MAXIS | 2021 – 2025 | Q1–Q4 |
| TNB | TNB | 2021 – 2025 | Q1–Q4 |

---

## Features

- **Idempotent backfill** — iterates every configured (year, quarter) and skips reports already on disk; safe to re-run at any time.
- **Latest-release check** — a fast `--latest` flag downloads only the most recently completed quarter for each company.
- **Automated scheduler** — `scheduler.py` runs the scraper on a weekly schedule (every Monday 09:00 MYT) without any manual intervention.
- **Stealth browser** — uses `playwright-stealth` and custom WebGL/navigator spoofing to bypass bot-detection (Imperva, Cloudflare, etc.).
- **Per-company DOM matching** — each scraper navigates the exact page structure (accordions, tab panels, iframes, year selectors) of its target site, so the correct quarter PDF is always selected regardless of filename conventions.
- **Comprehensive logging** — all activity is written to `scraper.log`; real-time progress is also printed to stdout.

---

## Requirements

- Python 3.8+
- Google Chrome installed (standard macOS path)

---

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/FinSight_API.git
   cd FinSight_API
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate        # macOS / Linux
   # venv\Scripts\activate.bat     # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright's Chrome browser**:
   ```bash
   playwright install chrome
   ```

---

## Usage

### Full backfill (recommended first run)
Downloads every missing report across all configured years and quarters. Reports already on disk are silently skipped.
```bash
python main.py
```

### Latest-quarter check (fast daily / weekly check)
Only checks whether the most recently completed quarter is available for each company.
```bash
python main.py --latest
```

### Automated scheduler
Runs in the foreground and triggers the scraper every **Monday at 09:00 MYT**. Also performs an immediate check on startup.
```bash
python scheduler.py
```

To run the scheduler in the background (persists after terminal close):
```bash
nohup python scheduler.py > scheduler_output.log 2>&1 &
```

---

## Project Structure

```
FinSight_API/
├── main.py              # Orchestrator: backfill logic, COMPANY_CONFIG, CLI flags
├── scheduler.py         # Automated weekly scheduler using the 'schedule' library
├── requirements.txt     # Python dependencies
├── scraper.log          # Appended log of all scraper activity
├── scrapers/
│   ├── __init__.py
│   ├── maybank.py       # Maybank IR page (JS-fetch PDF)
│   ├── cimb.py          # CIMB accordion DOM navigation
│   ├── sunway.py        # Sunway iframe-based report listing
│   ├── genting.py       # Genting tab-panel navigation
│   ├── telekom.py       # Telekom Malaysia iframe + date-prefix matching
│   ├── maxis.py         # Maxis year-filtered page + ordinal heading matching
│   ├── petronas.py      # Petronas year/quarter card matching (Q1, Q2/1H, Q4/2H)
│   └── tnb.py           # TNB JS table scan for PDF links
└── data/
    └── raw/
        ├── MAYBANK/     # MAYBANK_YYYY_QN.pdf
        ├── CIMB/        # CIMB_YYYY_QN.pdf
        ├── SUNWAY/      # SUNWAY_YYYY_QN.pdf
        ├── GENTING/     # GENTING_YYYY_QN.pdf
        ├── TELEKOM/     # TELEKOM_YYYY_QN.pdf
        ├── MAXIS/       # MAXIS_YYYY_QN.pdf
        ├── PETRONAS/    # PETRONAS_YYYY_QN.pdf
        └── TNB/         # TNB_YYYY_QN.pdf
```

---

## Configuration

To adjust which years are scraped, edit `COMPANY_CONFIG` in `main.py`:

```python
COMPANY_CONFIG = [
    {"module": maybank,  "start": 2020, "end": 2025, "quarters": ["Q1", "Q2", "Q3", "Q4"]},
    {"module": maxis,    "start": 2021, "end": 2025, "quarters": ["Q1", "Q2", "Q3", "Q4"]},
    # ... etc.
]
```

- `start` / `end` — inclusive year range to backfill
- `quarters` — which quarters to collect (Petronas Q3 is automatically skipped by its scraper since no standalone Q3 report exists)

To change the scheduler frequency, edit the `schedule` calls in `scheduler.py`.

---

## Notes on Specific Companies

| Company | Behaviour |
|---------|-----------|
| **Petronas** | Only publishes Q1, Q2 (or `1H`), and Q4 (or `2H`/full year). Q3 requests are skipped automatically. |
| **Maxis** | Reports are filtered by year via URL; matched by ordinal heading (`1st Quarter`, `2nd Quarter`, etc.). |
| **CIMB** | Uses an accordion layout per year; matched by `Interim Nth Quarter` button text — works across all historical naming conventions. |
| **Genting** | Large PDFs (~6 MB); download timeout is set to 5 minutes to accommodate the slow server. |

---

## Disclaimer

This tool is for educational and research purposes only. Ensure you comply with the Terms of Service of each respective website before use.
