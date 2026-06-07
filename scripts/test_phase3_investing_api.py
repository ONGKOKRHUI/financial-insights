#!/usr/bin/env python3
"""Call the Investing.com earnings API used by Phase 3 and print the JSON response.

Phase 3 resolves an instrument_id, then fetches:
  GET https://endpoints.investing.com/earnings/v1/instruments/{id}/earnings

The endpoint requires a guest Bearer JWT. Supply one via INVESTING_BEARER_TOKEN,
or the script bootstraps it from an Investing.com page with Playwright.

Usage:
    python scripts/test_phase3_investing_api.py
    python scripts/test_phase3_investing_api.py --ticker YTL --limit 10
    INVESTING_BEARER_TOKEN=eyJ... python scripts/test_phase3_investing_api.py --ticker TNB
    python scripts/test_phase3_investing_api.py --instrument-id 41640
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src" / "scraper"))

from ml_features.investing_com import (  # noqa: E402
    _API_HEADERS,
    _EARNINGS_API_BASE,
    _InvestingAuthSession,
    _get_instrument_id,
)
from ml_features.types import _INVESTING_EQUITY_SLUGS  # noqa: E402

_EARNINGS_URL = f"{_EARNINGS_API_BASE}/{{instrument_id}}/earnings"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test the Phase 3 Investing.com earnings API and print JSON.",
    )
    parser.add_argument(
        "--ticker",
        default="YTL",
        help="KLSE ticker symbol (default: YTL)",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="Company name for instrument_id search fallback",
    )
    parser.add_argument(
        "--instrument-id",
        type=int,
        default=None,
        help="Skip lookup and call the API with this instrument_id",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=8,
        help="Number of earnings rows to request (default: 8)",
    )
    return parser.parse_args()


def _resolve_instrument_id(
    ticker: str,
    *,
    description: str | None,
    instrument_id: int | None,
) -> int | None:
    if instrument_id is not None and instrument_id > 0:
        return instrument_id

    upper = ticker.upper()
    slug = _INVESTING_EQUITY_SLUGS.get(upper)
    return _get_instrument_id(upper, slug=slug, description=description)


def _fetch_raw_earnings_json(
    instrument_id: int,
    *,
    limit: int,
    bearer_token: str,
) -> tuple[int, dict | list | str]:
    url = _EARNINGS_URL.format(instrument_id=instrument_id)
    headers = {
        **_API_HEADERS,
        "Accept": "*/*",
        "Authorization": f"Bearer {bearer_token}",
    }
    resp = requests.get(
        url,
        params={"limit": limit},
        headers=headers,
        timeout=15,
    )
    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    return resp.status_code, body


def main() -> int:
    args = _parse_args()

    instrument_id = _resolve_instrument_id(
        args.ticker,
        description=args.description,
        instrument_id=args.instrument_id,
    )
    if instrument_id is None:
        print(
            json.dumps(
                {
                    "error": "instrument_id_not_found",
                    "ticker": args.ticker.upper(),
                    "message": "Could not resolve an Investing.com instrument_id",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    bearer = _InvestingAuthSession.get_bearer()
    if not bearer:
        print(
            json.dumps(
                {
                    "error": "bearer_token_unavailable",
                    "message": (
                        "Set INVESTING_BEARER_TOKEN or install Playwright "
                        "so the script can bootstrap a guest JWT"
                    ),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    status, body = _fetch_raw_earnings_json(
        instrument_id,
        limit=args.limit,
        bearer_token=bearer,
    )

    if status == 401:
        _InvestingAuthSession.reset()
        bearer = _InvestingAuthSession.get_bearer()
        if bearer:
            status, body = _fetch_raw_earnings_json(
                instrument_id,
                limit=args.limit,
                bearer_token=bearer,
            )

    if status != 200:
        print(
            json.dumps(
                {
                    "error": "api_request_failed",
                    "status_code": status,
                    "instrument_id": instrument_id,
                    "ticker": args.ticker.upper(),
                    "response": body,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(body, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
