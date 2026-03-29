import os
import logging
from urllib.parse import urljoin
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

URL = "https://www.tnb.com.my/suppliers-investors-media-relations/financial-info"
COMPANY = "TNB"
logger = logging.getLogger(COMPANY)


async def scrape(page, base_dir, year, quarter):
    """Scrape a single (year, quarter) report for TNB and save to disk."""
    company_dir = os.path.join(base_dir, COMPANY)
    os.makedirs(company_dir, exist_ok=True)

    save_path = os.path.join(company_dir, f"{COMPANY}_{year}_{quarter}.pdf")
    if os.path.exists(save_path):
        logger.info(f"Already exists, skipping: {save_path}")
        return

    logger.info(f"Scraping {COMPANY} {year} {quarter}...")
    try:
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        q_num = quarter[-1]  # '4' from 'Q4'

        # ALL rows are already in the DOM at load time; filter by JS
        target_href = await page.evaluate(f"""() => {{
            const links = document.querySelectorAll('table a[href]');
            const yearStr = '{year}';
            const qStr = 'Q{q_num}';
            for (const a of links) {{
                const text = a.innerText.trim();
                // Match "Financial Unaudited Results - 2024 - Q4"
                if (
                    text.toLowerCase().includes('financial unaudited') &&
                    text.includes(yearStr) &&
                    text.endsWith('- ' + qStr)
                ) {{
                    return a.getAttribute('href');
                }}
            }}
            return null;
        }}""")

        if not target_href:
            logger.warning(f"Could not find 'Financial Unaudited Results - {year} - {quarter}' – may not be published yet.")
            return

        full_pdf_url = urljoin(URL, target_href)

        logger.info(f"Found link: {full_pdf_url}. Downloading...")

        response = await page.context.request.get(
            full_pdf_url,
            headers={"Referer": URL},
            timeout=30000,
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