import os
import logging
from urllib.parse import urljoin

# The base domain – links in the HTML are root-relative (/content/dam/cimb/...)
BASE_URL = "https://www.cimb.com"
URL = f"{BASE_URL}/en/investor-relations/financial-information/cimb-group.html"
COMPANY = "CIMB"
logger = logging.getLogger(COMPANY)

# ---------------------------------------------------------------------------
# CIMB IR page structure (from live HTML inspection):
#
#   The page has one accordion per year, all rendered in the DOM (but hidden):
#     <div class="accordion-container ...">
#       <div class="accordion-btn ...">
#         <p class="accordion-title">2025 Financial Information</p>
#       </div>
#       <div class="accordion-content ...">          ← hidden, but in DOM
#         <!-- Q4 block -->
#         <div class="cmp-richText ...">
#           <h6>CIMB Group Unaudited Results for the 4th Quarter Ended 31 December 2025</h6>
#         </div>
#         <div class="cmp-ctabutton ..."><a href="...">Press Release</a></div>
#         <div class="cmp-ctabutton ..."><a href="...">Interim 4th Quarter</a></div>  ← FS
#         <div class="cmp-ctabutton ..."><a href="...">Analyst Presentation</a></div>
#         <!-- Q3 block starts next -->
#         <div class="cmp-richText ..."><h6>...3rd Quarter...</h6></div>
#         ...
#
# Strategy:
#   1. Find the .accordion-container whose .accordion-title contains "{year} Financial Information"
#   2. Inside it, find the <h6> containing "{ordinal} Quarter" (e.g. "1st Quarter")
#   3. Walk sibling elements after that <h6>'s parent until finding an <a> whose
#      text starts with "Interim" – that is the Financial Statement link
#   4. Resolve the root-relative href against BASE_URL and download
#
# Quarter ordinal map:
#   Q1 → "1st Quarter"   Q2 → "2nd Quarter"
#   Q3 → "3rd Quarter"   Q4 → "4th Quarter"
# ---------------------------------------------------------------------------

_ORDINALS = {"Q1": "1st", "Q2": "2nd", "Q3": "3rd", "Q4": "4th"}


async def scrape(page, base_dir, year, quarter):
    """Scrape the 'Interim Nth Quarter' Financial Statement PDF for CIMB."""
    company_dir = os.path.join(base_dir, COMPANY)
    os.makedirs(company_dir, exist_ok=True)

    save_path = os.path.join(company_dir, f"{COMPANY}_{year}_{quarter}.pdf")
    if os.path.exists(save_path):
        logger.info(f"Already exists, skipping: {save_path}")
        return

    logger.info(f"Scraping {COMPANY} {year} {quarter}...")
    try:
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)

        ordinal = _ORDINALS[quarter.upper()]          # e.g. "1st"
        year_label = f"{year} Financial Information"
        quarter_h6_keyword = f"{ordinal} Quarter"     # e.g. "1st Quarter"
        interim_text = f"Interim {ordinal} Quarter"   # e.g. "Interim 1st Quarter"

        # All accordion content is in the DOM even when collapsed, so we can
        # query without needing to click/expand.
        target_href = await page.evaluate(f"""() => {{
            const yearLabel    = {repr(year_label)};
            const h6Keyword    = {repr(quarter_h6_keyword)};
            const interimText  = {repr(interim_text)};

            // Find the accordion for this year
            const accordions = document.querySelectorAll('.accordion-container');
            for (const accordion of accordions) {{
                const titleEl = accordion.querySelector('.accordion-title');
                if (!titleEl || !titleEl.textContent.includes(yearLabel)) continue;

                // Loop through all h6 elements inside this accordion
                const h6s = accordion.querySelectorAll('h6');
                for (const h6 of h6s) {{
                    if (!h6.textContent.includes(h6Keyword)) continue;

                    // h6 → .cmp-text → .cmp-richText div
                    // The Press Release / Interim / Analyst buttons are
                    // *sibling* .cmp-ctabutton divs that follow this richText div.
                    const richText = h6.closest('.cmp-richText') ||
                                     h6.closest('[data-component="text"]')?.parentElement;
                    if (!richText) continue;

                    let sibling = richText.nextElementSibling;
                    while (sibling) {{
                        // Stop if we hit the next quarter's h6 block
                        if (sibling.querySelector('h6')) break;

                        const link = sibling.querySelector('a[href]');
                        if (link) {{
                            const txt = link.textContent.trim();
                            if (txt.toLowerCase().startsWith('interim')) {{
                                return link.getAttribute('href');
                            }}
                        }}
                        sibling = sibling.nextElementSibling;
                    }}
                }}
            }}
            return null;
        }}""")

        if not target_href:
            logger.warning(
                f"No 'Interim {ordinal} Quarter' link found for {year} {quarter} – "
                "quarter may not be published yet."
            )
            return

        # Href is root-relative: /content/dam/cimb/...
        full_pdf_url = urljoin(BASE_URL, target_href)
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