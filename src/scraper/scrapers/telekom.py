import os
import logging
from urllib.parse import urljoin

URL = "https://www.tm.com.my/investor-relations/financial-information/quarterly-results"
IFRAME_BASE_URL = "https://tm.listedcompany.com"
COMPANY = "TELEKOM"
logger = logging.getLogger(COMPANY)


async def scrape(page, base_dir, year, quarter):
    """Scrape a single (year, quarter) report for Telekom Malaysia and save to disk."""
    company_dir = os.path.join(base_dir, COMPANY)
    os.makedirs(company_dir, exist_ok=True)

    save_path = os.path.join(company_dir, f"{COMPANY}_{year}_{quarter}.pdf")
    if os.path.exists(save_path):
        logger.info(f"Already exists, skipping: {save_path}")
        return

    logger.info(f"Scraping {COMPANY} {year} {quarter}...")
    try:
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        frame_loc = page.frame_locator("#iframecontent")
        selector = "a[href*='quarterly_report'], a[href*='Quarterly_Report']"
        loc = frame_loc.locator(selector)

        try:
            await loc.first.wait_for(state="attached", timeout=15000)
        except Exception:
            logger.warning("Could not find any quarterly report links in the iframe DOM.")
            return

        target_href = None
        count = await loc.count()

        # Map quarters to TM's file-naming convention (ending month)
        q_months = {"Q1": "03", "Q2": "06", "Q3": "09", "Q4": "12"}
        target_month = q_months.get(quarter.upper(), "")

        # Pattern "202512" matches "quarterly_report_20251231.pdf"
        date_prefix = f"{year}{target_month}"

        for i in range(count):
            href = await loc.nth(i).get_attribute("href") or ""
            if date_prefix in href:
                target_href = href
                break

        if not target_href:
            logger.warning(f"Could not match {year} {quarter} inside the iframe – may not be published yet.")
            return

        full_pdf_url = urljoin(IFRAME_BASE_URL, target_href)

        logger.info(f"Found link: {full_pdf_url}. Downloading...")

        response = await page.context.request.get(full_pdf_url, headers={"Referer": IFRAME_BASE_URL}, timeout=30000)

        if response.ok:
            body = await response.body()
            with open(save_path, "wb") as f:
                f.write(body)
            logger.info(f"Successfully saved: {save_path}")
        else:
            logger.error(f"Server returned status {response.status}")

    except Exception as e:
        logger.error(f"Exception occurred for {year} {quarter}: {str(e)}")