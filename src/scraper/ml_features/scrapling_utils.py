"""Shared Scrapling browser fetch helpers for Cloudflare-protected sites."""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Site-specific defaults (Investing.com loads data in __NEXT_DATA__; CF solver often unnecessary)
_SITE_DEFAULTS: dict[str, dict[str, Any]] = {
    "investing.com": {
        "solve_cloudflare": False,
        "network_idle": False,
        "timeout": 90000,
        "wait": 3000,
    },
    "bursamalaysia.com": {
        "solve_cloudflare": False,
        "network_idle": True,
    },
}


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _chromium_binary_path(base: Path) -> Path | None:
    if not base.is_dir():
        return None
    patterns = (
        "chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    )
    for pattern in patterns:
        matches = sorted(base.glob(pattern), reverse=True)
        if matches:
            return matches[0]
    return None


def _ensure_browser_path() -> None:
    current = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    if current and _chromium_binary_path(Path(current)):
        return
    for path in (
        Path.home() / "Library/Caches/ms-playwright",
        Path.home() / ".cache/ms-playwright",
    ):
        if _chromium_binary_path(path):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(path)
            logger.debug("Using PLAYWRIGHT_BROWSERS_PATH=%s", path)
            return


def scrapling_session_kwargs(site: str | None = None) -> dict[str, Any]:
    """Options for Scrapling StealthyFetcher / AsyncStealthySession."""
    _ensure_browser_path()
    site_defaults = _SITE_DEFAULTS.get(site or {}, {})

    kwargs: dict[str, Any] = {
        "headless": _parse_bool_env("PLAYWRIGHT_HEADLESS", True),
        "solve_cloudflare": site_defaults.get(
            "solve_cloudflare",
            _parse_bool_env("SCRAPLING_SOLVE_CLOUDFLARE", True),
        ),
        "real_chrome": _parse_bool_env("SCRAPLING_REAL_CHROME", False),
        "network_idle": site_defaults.get(
            "network_idle",
            _parse_bool_env("SCRAPLING_NETWORK_IDLE", True),
        ),
        "load_dom": True,
        "google_search": False,
        "disable_resources": False,
        "timeout": site_defaults.get("timeout", 60000),
        "wait": site_defaults.get("wait", 1000),
        "locale": "en-US",
        "useragent": _USER_AGENT,
        "extra_flags": ["--no-sandbox", "--disable-dev-shm-usage"],
        "additional_args": {"viewport": {"width": 1280, "height": 900}},
    }

    if site == "investing.com":
        if os.getenv("INVESTING_SOLVE_CLOUDFLARE") is not None:
            kwargs["solve_cloudflare"] = _parse_bool_env("INVESTING_SOLVE_CLOUDFLARE", False)
        if os.getenv("INVESTING_NETWORK_IDLE") is not None:
            kwargs["network_idle"] = _parse_bool_env("INVESTING_NETWORK_IDLE", False)

    return kwargs


_JWT_RE = re.compile(
    r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
)


def _jwt_exp(token: str) -> float | None:
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        return float(exp) if exp is not None else None
    except Exception:  # noqa: BLE001
        return None


def _extract_bearer_from_html(html: str) -> str | None:
    """Pull the guest JWT embedded in Investing.com page HTML/scripts."""
    for match in _JWT_RE.finditer(html):
        token = match.group(0)
        exp = _jwt_exp(token)
        if exp is None or exp > time.time():
            return token
    return None


def bootstrap_investing_bearer_token(
    seed_url: str = "https://www.investing.com/equities/tenaga-nasional-bhd-earnings",
) -> str | None:
    """Load one Investing.com page and extract the guest JWT from HTML.

    The earnings API at ``endpoints.investing.com`` requires
    ``Authorization: Bearer <token>``.  Investing.com embeds a short-lived
    guest JWT in the page payload; after extracting it once we can call the
    JSON API directly with ``requests`` for every ticker.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        logger.info("Playwright not installed for Investing.com auth: %s", exc)
        return None

    _ensure_browser_path()
    browsers_root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""))
    if not browsers_root.is_dir():
        browsers_root = Path.home() / "Library/Caches/ms-playwright"
    executable = _chromium_binary_path(browsers_root)

    launch_kwargs: dict[str, Any] = {
        "headless": _parse_bool_env("PLAYWRIGHT_HEADLESS", True),
    }
    if executable:
        launch_kwargs["executable_path"] = str(executable)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_kwargs)
            context = browser.new_context(user_agent=_USER_AGENT)
            page = context.new_page()
            response = page.goto(seed_url, wait_until="domcontentloaded", timeout=120000)
            if response is not None and response.status >= 400:
                logger.warning(
                    "Investing.com bearer bootstrap page returned HTTP %s for %s",
                    response.status,
                    seed_url,
                )
                browser.close()
                return None

            token = _extract_bearer_from_html(page.content())
            browser.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Investing.com bearer bootstrap failed: %s", exc)
        return None

    if token:
        logger.info("Investing.com: extracted bearer token from page HTML")
        return token

    logger.warning("Investing.com: no bearer JWT found in page HTML")
    return None


def fetch_html_stealth(url: str, *, site: str | None = None) -> str | None:
    """Load a URL with Scrapling and return HTML, or None if unavailable."""
    if site is None and "investing.com" in url:
        site = "investing.com"

    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError as exc:
        logger.info("Scrapling not installed: %s", exc)
        return None

    kwargs = scrapling_session_kwargs(site=site)
    try:
        page = StealthyFetcher.fetch(url, **kwargs)
    except Exception as exc:  # noqa: BLE001
        if not kwargs.get("real_chrome"):
            logger.warning(
                "Scrapling fetch failed for %s (%s); retrying with real_chrome",
                url,
                exc,
            )
            try:
                retry = {**kwargs, "real_chrome": True}
                page = StealthyFetcher.fetch(url, **retry)
            except Exception as retry_exc:  # noqa: BLE001
                logger.warning("Scrapling retry failed for %s: %s", url, retry_exc)
                return None
        else:
            logger.warning("Scrapling fetch failed for %s: %s", url, exc)
            return None

    if hasattr(page, "html_content"):
        return page.html_content
    if hasattr(page, "text"):
        return page.text
    return str(page)


def fetch_pdf_stealth(pdf_url: str, *, referer: str) -> bytes | None:
    """Download PDF bytes via Playwright after loading the referer disclosure page.

    Bursa disclosure PDF URLs are Cloudflare-protected; a plain ``requests`` GET
    returns 403. Loading the announcement HTML first, then navigating to the
    attachment URL in the same browser session, captures the underlying PDF
    response (including Chrome's internal PDF viewer fetch).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        logger.info("Playwright not installed for PDF download: %s", exc)
        return None

    _ensure_browser_path()
    browsers_root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""))
    if not browsers_root.is_dir():
        browsers_root = Path.home() / "Library/Caches/ms-playwright"
    executable = _chromium_binary_path(browsers_root)

    captured_pdf: bytes | None = None

    def _capture_pdf(body: bytes) -> None:
        nonlocal captured_pdf
        if body.startswith(b"%PDF") and (captured_pdf is None or len(body) > len(captured_pdf)):
            captured_pdf = body

    launch_kwargs: dict[str, Any] = {
        "headless": _parse_bool_env("PLAYWRIGHT_HEADLESS", True),
    }
    if executable:
        launch_kwargs["executable_path"] = str(executable)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_kwargs)
            context = browser.new_context(user_agent=_USER_AGENT)
            page = context.new_page()

            def _on_response(response: Any) -> None:
                if response.status != 200:
                    return
                try:
                    _capture_pdf(response.body())
                except Exception:  # noqa: BLE001
                    return

            page.on("response", _on_response)
            page.goto(referer, wait_until="networkidle", timeout=90000)
            page.goto(pdf_url, wait_until="networkidle", timeout=90000)
            browser.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Playwright PDF download failed for %s: %s", pdf_url, exc)
        return None

    return captured_pdf
