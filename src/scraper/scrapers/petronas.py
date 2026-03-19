import os
import logging
from urllib.parse import urljoin

URL = "https://www.petronas.com/investor-relations/financial-results"
COMPANY = "PETRONAS"
logger = logging.getLogger(COMPANY)

# ---------------------------------------------------------------------------
# Petronas IR page structure (from live HTML inspection):
#
#   The page lists ALL years at once in stacked <div class="row"> blocks.
#   Each row covers one year. The first column has:
#       <div class="financial-reports-year">Year 2024</div>
#   Subsequent columns have &nbsp; as the year label.
#
#   Each column also contains a <div class="financial-reports-card"> with:
#       <h4><strong>Q1</strong> | May 31, 2024</h4>   ← quarter label
#       <p><strong><a href="...">Financial Report</a></strong></p>
#       <p><strong><a href="...">Press Release</a></strong></p>
#       <p><strong><a href="...">Financial Operational Report</a></strong></p>
#
#   IMPORTANT — Petronas does NOT publish quarterly (Q1–Q4) uniformly:
#     • 2024:  Q1  |  Q2 (1H interim)  |  Q4 (Full Year)   — no Q3
#     • 2025:  1H  |  2H (Full Year)                        — no Q1/Q3
#   Older years likely follow a similar Q1 / 1H / Full-Year pattern.
#
# Quarter → heading mapping (case-insensitive prefix match on <h4><strong>):
#   Q1 → "q1"
#   Q2 → "q2"  OR  "1h"   (Petronas labels their half-year as 1H)
#   Q3 → not published — skip gracefully
#   Q4 → "q4"  OR  "2h"   (full-year / 2H label)
# ---------------------------------------------------------------------------

_QUARTER_HEADERS = {
    "Q1": ["q1"],
    "Q2": ["q2", "1h"],
    "Q3": [],             # Petronas never publishes a standalone Q3 report
    "Q4": ["q4", "2h"],
}


async def scrape(page, base_dir, year, quarter):
    """Scrape the 'Financial Report' PDF for Petronas for a given (year, quarter)."""
    company_dir = os.path.join(base_dir, COMPANY)
    os.makedirs(company_dir, exist_ok=True)

    save_path = os.path.join(company_dir, f"{COMPANY}_{year}_{quarter}.pdf")
    if os.path.exists(save_path):
        logger.info(f"Already exists, skipping: {save_path}")
        return

    # Petronas does not publish a standalone Q3 report
    valid_headings = _QUARTER_HEADERS.get(quarter.upper(), [])
    if not valid_headings:
        logger.info(
            f"Skipping {COMPANY} {year} {quarter} – "
            "Petronas does not publish a standalone Q3 report."
        )
        return

    logger.info(f"Scraping {COMPANY} {year} {quarter}...")
    try:
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)

        # Build a JS list of valid heading strings to match against
        headings_js = str(valid_headings)   # e.g. "['q2', '1h']"

        # Walk the DOM:
        # 1. Find .financial-reports-year element whose text is "Year {year}"
        # 2. Find the parent .row for that element
        # 3. Loop through all .financial-reports-card in that row
        # 4. Check if the card's <h4><strong> text starts with one of our headings
        # 5. Within the matching card, find the <a> whose link text = "Financial Report"
        target_href = await page.evaluate(f"""() => {{
            const targetYear = 'Year {year}';
            const validHeadings = {headings_js};

            // Find the year label element
            const yearDivs = document.querySelectorAll('.financial-reports-year');
            let targetRow = null;
            for (const div of yearDivs) {{
                if (div.textContent.trim() === targetYear) {{
                    targetRow = div.closest('.row');
                    break;
                }}
            }}
            if (!targetRow) return null;

            // Loop through every financial-reports-card in this row
            const cards = targetRow.querySelectorAll('.financial-reports-card');
            for (const card of cards) {{
                const strong = card.querySelector('h4 strong');
                if (!strong) continue;

                const label = strong.textContent.trim().toLowerCase();
                const matched = validHeadings.some(h => label === h || label.startsWith(h));
                if (!matched) continue;

                // Found the right card — now get the "Financial Report" link
                const allLinks = card.querySelectorAll('p strong a[href]');
                for (const link of allLinks) {{
                    if (link.textContent.trim().toLowerCase() === 'financial report') {{
                        return link.getAttribute('href');
                    }}
                }}
            }}
            return null;
        }}""")

        if not target_href:
            logger.warning(
                f"No 'Financial Report' link found for {year} {quarter} – "
                "report may not be published yet or the year doesn't exist on the page."
            )
            return

        full_pdf_url = urljoin(URL, target_href)
        logger.info(f"Found link: {full_pdf_url}. Downloading...")

        response = await page.context.request.get(
            full_pdf_url,
            headers={"Referer": URL},
            timeout=60000,
        )

        if response.ok:
            body = await response.body()
            with open(save_path, "wb") as f:
                f.write(body)
            logger.info(f"Successfully saved: {save_path}")
        else:
            logger.error(f"Server returned status {response.status} for {full_pdf_url}")

    except Exception as e:
        logger.error(f"Exception occurred for {year} {quarter}: {str(e)}")