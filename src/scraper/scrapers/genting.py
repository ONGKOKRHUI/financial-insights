import os
import logging
from urllib.parse import urljoin
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

URL = "https://www.genting.com/quarterly-reports/"
COMPANY = "GENTING"
logger = logging.getLogger(COMPANY)


async def scrape(page, base_dir, year, quarter):
    """Scrape a single (year, quarter) report for Genting and save to disk."""
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

        q_num = quarter[-1]
        ordinals = {"1": "1st", "2": "2nd", "3": "3rd", "4": "4th"}
        ordinal = ordinals.get(q_num, f"{q_num}th")

        year_short = str(year)[-2:]  # "2024" → "24"

        # Activate the correct tab panel via JavaScript
        activated = await page.evaluate(f"""() => {{
            document.querySelectorAll('div.tab-pane').forEach(el => {{
                el.classList.remove('active', 'in');
            }});
            const panel = document.getElementById('{year_short}');
            if (!panel) return false;
            panel.classList.add('active', 'in');
            return true;
        }}""")

        if not activated:
            logger.warning(f"Could not find tab panel id='{year_short}' for {year} – year may not exist.")
            return

        logger.info(f"Activated tab panel #{year_short} for {year}.")
        await page.wait_for_timeout(500)

        target_href = await page.evaluate(f"""() => {{
            const panel = document.getElementById('{year_short}');
            if (!panel) return null;
            const listItems = panel.querySelectorAll('li');
            const ordinal = '{ordinal}';
            for (const li of listItems) {{
                const h4 = li.querySelector('h4');
                if (h4 && h4.innerText.toLowerCase().includes(ordinal.toLowerCase())) {{
                    const a = li.querySelector('a[href]');
                    if (a) return a.getAttribute('href');
                }}
            }}
            const allLinks = panel.querySelectorAll('a[href*=".pdf"]');
            for (const a of allLinks) {{
                const parentText = (a.closest('li') || a).innerText.toLowerCase();
                if (parentText.includes(ordinal.toLowerCase())) {{
                    return a.getAttribute('href');
                }}
            }}
            return null;
        }}""")

        if not target_href:
            logger.warning(f"Could not find PDF link for {ordinal} Quarterly Report {year}.")
            return

        full_pdf_url = urljoin(URL, target_href)

        logger.info(f"Found link: {full_pdf_url}. Downloading...")

        response = await page.context.request.get(
            full_pdf_url,
            headers={"Referer": URL},
            timeout=300000,   # 5 min – Genting's server is slow for large PDFs (~6 MB)
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