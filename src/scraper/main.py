"""
FinSight Scraper — Main Orchestrator
=====================================
Behaviour
---------
1. BACKFILL MODE (default)
   Iterates every (year, quarter) combination within each company's configured
   date range.  If the PDF already exists on disk it is silently skipped,
   so re-runs are fully idempotent.

2. NEW-RELEASE CHECK (always runs after backfill)
   For each company, the scraper also attempts to download the most recent
   quarter that *should* exist based on today's date, catching brand-new
   releases automatically.

Running
-------
    python main.py            # backfill all missing + check latest
    python main.py --latest   # check ONLY the current quarter (fast daily check)

Scheduler
---------
For automated daily / weekly checks, use the companion scheduler.py:
    python scheduler.py
"""

import asyncio
import os
import sys
import logging
from datetime import date
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from scrapers import (
    maybank, cimb, tnb, petronas,
    maxis, telekom, genting, sunway,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    filename="scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# Mirror logs to stdout so you can see progress in real time
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
logging.getLogger("").addHandler(console)

BASE_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")

# ---------------------------------------------------------------------------
# Per-company scraper config
#   module   : the scraper module to call
#   start    : oldest year to include (inclusive)
#   end      : newest year to include (inclusive)
#   quarters : which quarters to collect (Q1–Q4 for most; some have gaps)
# ---------------------------------------------------------------------------
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


def current_quarter() -> tuple[int, str]:
    """Return the most recently *completed* quarter as (year, 'Q#')."""
    today = date.today()
    # A quarter is considered 'released' roughly 1–2 months after period end.
    # We use a conservative 45-day lag from quarter-end.
    if today.month <= 3:
        return today.year - 1, "Q4"
    elif today.month <= 6:
        return today.year, "Q1"
    elif today.month <= 9:
        return today.year, "Q2"
    else:
        return today.year, "Q3"


def build_todo_list(config: dict, latest_only: bool = False) -> list[tuple[int, str]]:
    """
    Return a list of (year, quarter) tuples that are MISSING from disk
    for the given company config.
    """
    company_dir = os.path.join(BASE_DIR, config["module"].COMPANY)
    existing = set(os.listdir(company_dir)) if os.path.exists(company_dir) else set()

    if latest_only:
        yr, qtr = current_quarter()
        items = [(yr, qtr)]
    else:
        items = [
            (yr, qtr)
            for yr in range(config["start"], config["end"] + 1)
            for qtr in config["quarters"]
        ]

    return [
        (yr, qtr)
        for yr, qtr in items
        if f"{config['module'].COMPANY}_{yr}_{qtr}.pdf" not in existing
    ]


async def run_scraper(context, config, latest_only=False):
    """Run one company's scraper for all missing (year, quarter) combos."""
    module = config["module"]
    todo = build_todo_list(config, latest_only)

    if not todo:
        logging.getLogger("MAIN").info(
            f"{module.COMPANY}: all reports already on disk – nothing to do."
        )
        return

    logging.getLogger("MAIN").info(
        f"{module.COMPANY}: {len(todo)} reports to download → {todo}"
    )

    for year, quarter in todo:
        page = await context.new_page()
        try:
            await module.scrape(page, BASE_DIR, year, quarter)
        except Exception as e:
            logging.getLogger("MAIN").error(
                f"Error scraping {module.COMPANY} {year} {quarter}: {e}"
            )
        finally:
            await page.close()


async def main(latest_only: bool = False):
    async with Stealth().use_async(async_playwright()) as p:
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

        # Spoof WebGL renderer so Imperva doesn't flag us as headless
        await context.add_init_script("""
        (() => {
            const patchWebGL = (Klass) => {
                if (typeof Klass === 'undefined') return;
                const orig = Klass.prototype.getParameter;
                Klass.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Apple Inc.';
                    if (parameter === 37446) return 'ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)';
                    return orig.call(this, parameter);
                };
            };
            patchWebGL(WebGLRenderingContext);
            if (typeof WebGL2RenderingContext !== 'undefined') patchWebGL(WebGL2RenderingContext);
            try { Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 }); } catch(e) {}
            try { Object.defineProperty(navigator, 'deviceMemory',        { get: () => 8 }); } catch(e) {}
            try { Object.defineProperty(navigator, 'platform',            { get: () => 'MacIntel' }); } catch(e) {}
        })();
        """)

        context.set_default_timeout(60000)

        mode = "latest-only" if latest_only else "full backfill"
        logging.getLogger("MAIN").info(f"Starting FinSight scraper in [{mode}] mode.")

        for config in COMPANY_CONFIG:
            try:
                await run_scraper(context, config, latest_only=latest_only)
            except Exception as e:
                logging.getLogger("MAIN").error(
                    f"Fatal error for {config['module'].COMPANY}: {e}"
                )

        await browser.close()
        logging.getLogger("MAIN").info("All done.")


if __name__ == "__main__":
    latest_only = "--latest" in sys.argv
    asyncio.run(main(latest_only=latest_only))