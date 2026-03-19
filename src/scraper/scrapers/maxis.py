import os
import logging
from urllib.parse import urljoin

BASE_URL = "https://maxis.listedcompany.com"
URL = f"{BASE_URL}/financials.html"
COMPANY = "MAXIS"
logger = logging.getLogger(COMPANY)

# ---------------------------------------------------------------------------
# Maxis IR page structure (from live HTML inspection):
#
#   URL to load year: https://maxis.listedcompany.com/financials.html/year/{YYYY}
#
#   Each quarter is a <div class="qr-list"> block:
#     <h4 class="green-text">4th Quarter 2025</h4>
#     <div class="financial_archive year_2025 row">
#       <div class="col financials_card">
#         <div class="fc-name">Financial Statement</div>
#         <div class="cta-button ...">
#           <a href="https://ir.listedcompany.com/tracker.pl?...&redirect=...quarterly_report_31122025.pdf">
#
# The tracker URL redirects to the actual PDF, so we can download it directly.
#
# Quarter ordinal headings:
#   Q1 → "1st Quarter"   Q2 → "2nd Quarter"
#   Q3 → "3rd Quarter"   Q4 → "4th Quarter"
# ---------------------------------------------------------------------------

_ORDINALS = {"Q1": "1st", "Q2": "2nd", "Q3": "3rd", "Q4": "4th"}


async def scrape(page, base_dir, year, quarter):
    """Scrape a single (year, quarter) Financial Statement for Maxis."""
    company_dir = os.path.join(base_dir, COMPANY)
    os.makedirs(company_dir, exist_ok=True)

    save_path = os.path.join(company_dir, f"{COMPANY}_{year}_{quarter}.pdf")
    if os.path.exists(save_path):
        logger.info(f"Already exists, skipping: {save_path}")
        return

    logger.info(f"Scraping {COMPANY} {year} {quarter}...")

    # Navigate to the year-filtered page so only that year's sections are rendered
    year_url = f"{URL}/year/{year}"
    try:
        await page.goto(year_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)

        ordinal = _ORDINALS[quarter.upper()]
        heading_text = f"{ordinal} Quarter {year}"

        # Use JS to walk the DOM:
        # 1. Find the .qr-list whose h4 matches our heading
        # 2. Inside it, find the .financials_card where .fc-name = "Financial Statement"
        # 3. Return the <a> href in that card
        target_href = await page.evaluate(f"""() => {{
            const heading = '{heading_text}';
            const lists = document.querySelectorAll('div.qr-list');
            for (const list of lists) {{
                const h4 = list.querySelector('h4');
                if (!h4 || !h4.innerText.trim().toLowerCase().includes(heading.toLowerCase())) continue;

                // Find all financials_card divs inside this block
                const cards = list.querySelectorAll('.financials_card');
                for (const card of cards) {{
                    const label = card.querySelector('.fc-name');
                    if (label && label.innerText.trim().toLowerCase() === 'financial statement') {{
                        const link = card.querySelector('a[href]');
                        if (link) return link.getAttribute('href');
                    }}
                }}
            }}
            return null;
        }}""")

        if not target_href:
            logger.warning(
                f"No Financial Statement link found for {heading_text} – "
                "quarter may not be published yet."
            )
            return

        logger.info(f"Found link: {target_href}. Downloading...")

        # The tracker URL itself redirects to the actual PDF; Playwright follows redirects
        response = await page.context.request.get(
            target_href,
            headers={"Referer": year_url},
            timeout=60000,
        )

        if response.ok:
            body = await response.body()
            with open(save_path, "wb") as f:
                f.write(body)
            logger.info(f"Successfully saved: {save_path}")
        else:
            logger.error(f"Server returned status {response.status} for {target_href}")

    except Exception as e:
        logger.error(f"Exception occurred for {year} {quarter}: {str(e)}")