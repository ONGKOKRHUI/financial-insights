import asyncio
import os
import logging
from urllib.parse import urljoin
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

URL = "https://www.maybank.com/en/investor-relations/financial-overview/quarterly-announcements.page"
COMPANY = "MAYBANK"
logger = logging.getLogger(COMPANY)

_MAX_RETRIES = 3          # total attempts per quarter
_DOWNLOAD_TIMEOUT = 120000  # 120 s – large PDFs can be slow over Imperva CDN
_RETRY_WAIT = 15          # seconds to pause between retries (lets WAF rate-limit window reset)


async def _resolve_pdf_url(page, year, quarter):
    """Navigate to the IR page, select the year, and return the resolved PDF URL.

    Returns the full PDF URL string, or None if the link cannot be found.
    """
    fy_value = f"FY{year}"

    await page.goto(URL, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(5000)

    # Simulate human scrolling to feed Imperva's behavioural scoring.
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
        return None

    await select_loc.select_option(value=fy_value)
    logger.info(f"Selected year {fy_value} in the filter dropdown.")
    await page.wait_for_timeout(1500)

    fy_count = await page.locator(f".{fy_value}").count()
    if fy_count == 0:
        logger.warning(f"Year container .{fy_value} not found – this year may not exist on the website.")
        return None

    link_selector = (
        f".{fy_value} .link-item:has(h6:text-is('Financial Statements'))"
        f" a:text-is('{quarter}')"
    )
    loc = page.locator(link_selector).first

    try:
        await loc.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError:
        logger.warning(f"Link not found for {year} {quarter} – quarter may not be published yet.")
        return None

    download_url = await loc.get_attribute("href")
    if not download_url:
        logger.error(f"No href attribute found for {year} {quarter}.")
        return None

    full_pdf_url = urljoin(URL, download_url)

    # Hover over the link to boost Imperva's behavioural score before downloading.
    await loc.scroll_into_view_if_needed()
    await page.wait_for_timeout(800)
    await loc.hover()
    await page.wait_for_timeout(600)

    return full_pdf_url


async def scrape(page, base_dir, year, quarter):
    """Scrape a single (year, quarter) report for Maybank and save to disk."""
    company_dir = os.path.join(base_dir, COMPANY)
    os.makedirs(company_dir, exist_ok=True)

    save_path = os.path.join(company_dir, f"{COMPANY}_{year}_{quarter}.pdf")
    if os.path.exists(save_path):
        logger.info(f"Already exists, skipping: {save_path}")
        return

    logger.info(f"Scraping {COMPANY} {year} {quarter}...")

    # Resolve the PDF URL once (no retry needed here – page navigation issues are
    # usually WAF blocks that retrying immediately won't help).
    try:
        full_pdf_url = await _resolve_pdf_url(page, year, quarter)
    except Exception as e:
        logger.error(f"Exception while resolving PDF URL for {year} {quarter}: {e}")
        return

    if not full_pdf_url:
        return  # warning/error already logged inside _resolve_pdf_url

    logger.info(f"Found link: {full_pdf_url}. Downloading via browser context request...")

    # --- Download with retry ---
    # Imperva CDN sometimes tarpits chunked transfers: the server returns 200 OK
    # but then throttles or aborts the body stream, causing timeouts/aborts.
    # Re-navigating the page refreshes the Imperva session token (reese84 cookie)
    # before each retry, which is usually enough to get a clean connection.
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await page.context.request.get(
                full_pdf_url,
                headers={"Referer": URL},
                timeout=_DOWNLOAD_TIMEOUT,
            )

            if not response.ok:
                logger.error(
                    f"[Attempt {attempt}/{_MAX_RETRIES}] Server returned HTTP "
                    f"{response.status} for {full_pdf_url}"
                )
                break  # a non-200 status won't improve with retries

            pdf_bytes = await response.body()

            # Validate that we actually received a PDF (magic bytes: %PDF).
            if not pdf_bytes.startswith(b"%PDF"):
                logger.error(
                    f"[Attempt {attempt}/{_MAX_RETRIES}] Downloaded content for "
                    f"{year} {quarter} is not a valid PDF "
                    f"(got {len(pdf_bytes)} bytes, starts with: {pdf_bytes[:20]}). "
                    "Possible WAF block or redirect — skipping save."
                )
                break  # receiving HTML instead of PDF won't improve on retry

            with open(save_path, "wb") as f:
                f.write(pdf_bytes)

            logger.info(
                f"Successfully saved: {save_path} ({len(pdf_bytes):,} bytes)"
            )
            return  # success – done

        except Exception as e:
            err_str = str(e).split("\n")[0]  # first line only (avoids verbose call log)
            if attempt < _MAX_RETRIES:
                logger.warning(
                    f"[Attempt {attempt}/{_MAX_RETRIES}] Download failed for "
                    f"{year} {quarter}: {err_str}. "
                    f"Waiting {_RETRY_WAIT}s then refreshing session and retrying..."
                )
                await asyncio.sleep(_RETRY_WAIT)
                # Re-navigate to refresh Imperva session cookies before next attempt.
                try:
                    await page.goto(URL, wait_until="networkidle", timeout=60000)
                    await page.wait_for_timeout(4000)
                except Exception:
                    pass  # best-effort; proceed to retry regardless
            else:
                logger.error(
                    f"[Attempt {attempt}/{_MAX_RETRIES}] Download failed for "
                    f"{year} {quarter} after {_MAX_RETRIES} attempts: {err_str}"
                )
