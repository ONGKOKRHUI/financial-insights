import os
import logging
from urllib.parse import urljoin
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

URL = "https://www.maybank.com/en/investor-relations/financial-overview/quarterly-announcements.page"
COMPANY = "MAYBANK"
logger = logging.getLogger(COMPANY)


async def scrape(page, base_dir, year, quarter):
    company_dir = os.path.join(base_dir, COMPANY)
    os.makedirs(company_dir, exist_ok=True)

    logger.info(f"Navigating to {URL}...")
    try:
        fy_value = f"FY{year}"

        # wait_until="networkidle" gives Imperva's background scripts time to execute
        await page.goto(URL, wait_until="networkidle", timeout=60000)

        # Allow Imperva WAF JS challenge to fully resolve before interacting
        await page.wait_for_timeout(5000)

        # Ensure the dropdown exists and select the target year to unhide the container
        dropdown_selector = "select.filter-label"
        if await page.locator(dropdown_selector).is_visible():
            await page.select_option(dropdown_selector, value=fy_value)
            await page.wait_for_timeout(2000)  # Give jQuery time to update the DOM
        else:
            logger.warning("Dropdown not visible, WAF might still be active.")

        # Construct a strict selector matching the specific year and quarter based on Maybank's DOM
        link_selector = (
            f"div.link-list.{fy_value} "
            f"div.link-item:has(h6:text-is('Financial Statements')) "
            f"a.btn-link:text-is('{quarter}')"
        )
        
        loc = page.locator(link_selector).first

        try:
            # Wait for the element to be visible, not just attached
            await loc.wait_for(state="visible", timeout=15000)
        except PlaywrightTimeoutError:
            logger.error(f"Could not find link for {year} {quarter}. WAF block active or link not in DOM.")
            return

        # Extract the relative URL and build the absolute URL
        download_url = await loc.get_attribute("href")
        if not download_url:
            logger.error(f"No href attribute found for {year} {quarter}.")
            return

        full_pdf_url = urljoin(URL, download_url)
        file_name = f"{COMPANY}_{year}_{quarter}.pdf"
        save_path = os.path.join(company_dir, file_name)

        # Scroll to and hover over the link to feed Imperva's behavioral scoring
        await loc.scroll_into_view_if_needed()
        await page.wait_for_timeout(800)
        await loc.hover()
        await page.wait_for_timeout(500)

        logger.info(f"Found link: {full_pdf_url}. Injecting iframe to capture PDF bytes safely...")

        try:
            # We use expect_response to catch the network response of the iframe navigating to the PDF
            async with page.expect_response(
                lambda r: r.url == full_pdf_url and r.status == 200 and r.request.method == 'GET', 
                timeout=60000
            ) as resp_info:
                
                # Inject a hidden iframe pointing to the PDF.
                # This forces the browser to fetch the PDF using standard navigation headers 
                # rather than headless download APIs, completely bypassing the WAF rules.
                await page.evaluate(f"""() => {{
                    const iframe = document.createElement('iframe');
                    iframe.style.display = 'none';
                    iframe.src = '{full_pdf_url}';
                    document.body.appendChild(iframe);
                }}""")

            response = await resp_info.value
            
            # Extract the raw binary data directly from the network response
            pdf_bytes = await response.body()

            with open(save_path, "wb") as f:
                f.write(pdf_bytes)

            logger.info(f"Successfully saved: {save_path}")

        except PlaywrightTimeoutError:
            logger.error(f"Iframe navigation timed out for {year} {quarter}. The WAF might be tarpitting the specific PDF endpoint.")
            
    except Exception as e:
        logger.error(f"Exception occurred: {str(e)}")