import os
import logging
from urllib.parse import urljoin

URL = "https://www.sunway.com.my/investor-relations/reports-publications/"
IFRAME_BASE_URL = "https://ir2.chartnexus.com/sunway/investor-relations/ir-reports-publications.php"
COMPANY = "SUNWAY"
logger = logging.getLogger(COMPANY)


async def scrape(page, base_dir, year, quarter):
    """Scrape a single (year, quarter) report for Sunway and save to disk."""
    company_dir = os.path.join(base_dir, COMPANY)
    os.makedirs(company_dir, exist_ok=True)

    save_path = os.path.join(company_dir, f"{COMPANY}_{year}_{quarter}.pdf")
    if os.path.exists(save_path):
        logger.info(f"Already exists, skipping: {save_path}")
        return

    logger.info(f"Scraping {COMPANY} {year} {quarter}...")
    try:
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        q_num = quarter[-1]

        frame_loc = page.frame_locator("#investor-iframe")
        selector = "a.btn-arrow, a[href*='.pdf'], a[href*='quarterly']"

        target_href = None

        for _ in range(20):
            loc = frame_loc.locator(selector)
            count = await loc.count()

            for i in range(count):
                element = loc.nth(i)
                href = await element.get_attribute("href") or ""
                text = await element.inner_text() or ""

                href_lower = href.lower()
                text_lower = text.lower()

                if str(year) in href_lower or str(year) in text_lower:
                    if (f"q{q_num}" in href_lower or f"{q_num}q" in href_lower
                            or f"quarter {q_num}" in text_lower or quarter.lower() in text_lower):
                        if ".pdf" in href_lower or "quarterly" in href_lower:
                            target_href = href
                            break

            if target_href:
                break

            await page.wait_for_timeout(1000)

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