import os
import logging
from urllib.parse import urljoin
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

URL = "https://www.maybank.com/en/investor-relations/financial-overview/quarterly-announcements.page"
COMPANY = "MAYBANK"
logger = logging.getLogger(COMPANY)


async def scrape(page, base_dir, year, quarter):
    """Scrape a single (year, quarter) report for Maybank and save to disk."""
    company_dir = os.path.join(base_dir, COMPANY)
    os.makedirs(company_dir, exist_ok=True)

    save_path = os.path.join(company_dir, f"{COMPANY}_{year}_{quarter}.pdf")
    if os.path.exists(save_path):
        logger.info(f"Already exists, skipping: {save_path}")
        return

    logger.info(f"Scraping {COMPANY} {year} {quarter}...")
    try:
        fy_value = f"FY{year}"

        await page.goto(URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # Simulate human scrolling behaviour.
        await page.evaluate("window.scrollTo({top: 400, behavior: 'smooth'})")
        await page.wait_for_timeout(1200)
        await page.evaluate("window.scrollTo({top: 800, behavior: 'smooth'})")
        await page.wait_for_timeout(1200)
        await page.evaluate("window.scrollTo({top: 400, behavior: 'smooth'})")
        await page.wait_for_timeout(800)

        select_loc = page.locator("select.filter-label").first
        try:
            await select_loc.wait_for(state="visible", timeout=20000)
        except PlaywrightTimeoutError:
            logger.error("Year <select> not found or not visible. Possible WAF block.")
            return

        await select_loc.select_option(value=fy_value)
        logger.info(f"Selected year {fy_value} in the filter dropdown.")
        await page.wait_for_timeout(1500)

        fy_count = await page.locator(f".{fy_value}").count()
        if fy_count == 0:
            logger.warning(f"Year container .{fy_value} not found – this year may not exist on the website.")
            return

        link_selector = (
            f".{fy_value} .link-item:has(h6:text-is('Financial Statements'))"
            f" a:text-is('{quarter}')"
        )
        loc = page.locator(link_selector).first

        try:
            await loc.wait_for(state="visible", timeout=15000)
        except PlaywrightTimeoutError:
            logger.warning(f"Link not found for {year} {quarter} – quarter may not be published yet.")
            return

        download_url = await loc.get_attribute("href")
        if not download_url:
            logger.error(f"No href attribute found for {year} {quarter}.")
            return

        full_pdf_url = urljoin(URL, download_url)

        await loc.scroll_into_view_if_needed()
        await page.wait_for_timeout(800)
        await loc.hover()
        await page.wait_for_timeout(600)

        logger.info(f"Found link: {full_pdf_url}. Injecting iframe to capture PDF bytes...")

        try:
            async with page.expect_response(
                lambda r: r.url == full_pdf_url and r.status == 200 and r.request.method == 'GET',
                timeout=60000
            ) as resp_info:
                await page.evaluate(f"""() => {{
                    const iframe = document.createElement('iframe');
                    iframe.style.display = 'none';
                    iframe.src = '{full_pdf_url}';
                    document.body.appendChild(iframe);
                }}""")

            response = await resp_info.value
            pdf_bytes = await response.body()

            with open(save_path, "wb") as f:
                f.write(pdf_bytes)

            logger.info(f"Successfully saved: {save_path}")

        except PlaywrightTimeoutError:
            logger.error(f"Iframe navigation timed out for {year} {quarter}.")

    except Exception as e:
        logger.error(f"Exception occurred for {year} {quarter}: {str(e)}")
