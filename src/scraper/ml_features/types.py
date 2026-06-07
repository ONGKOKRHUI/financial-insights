"""Shared data classes for the ML feature extraction pipeline."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# Bursa numeric codes for yfinance (name tickers like MAYBANK.KL return empty data).
_KLSE_YFINANCE_CODES: dict[str, str] = {
    "MAYBANK": "1155",
    "CIMB": "1023",
    "SUNWAY": "5211",
    "GENTING": "3182",
    "TELEKOM": "4863",
    "MAXIS": "6012",
    "TNB": "5347",
    "YTLPOWR": "6742",
    "PETGAS": "6033",
    "YTL": "4677",
    "GASMSIA": "5209",
    "MFCB": "3069",
    "RANHILL": "5272",
    "TENAGA": "5347",
    "PBBANK": "1295",
    "DIGI": "6947",
    "AXIATA": "6888",
    "MISC": "3816",
    "PCHEM": "5183",
    "DIALOG": "7277",
    "IHH": "5225",
    "HARTA": "5168",
    "TOPGLOV": "7113",
}

# Investing.com equity URL slugs (…/equities/{slug}-earnings).
_INVESTING_EQUITY_SLUGS: dict[str, str] = {
    "MAYBANK": "malayan-banking-bhd",
    "CIMB": "cimb-group-holdings",
    "SUNWAY": "sunway",
    "GENTING": "genting",
    "TELEKOM": "telekom-malaysia-bhd",
    "MAXIS": "maxis-bhd",
    "TNB": "tenaga-nasional-bhd",
    "YTLPOWR": "ytl-power-international-bhd",
    "PETGAS": "petronas-gas-bhd",
    "YTL": "ytl-corp-bhd",
    "GASMSIA": "gas-malaysia-bhd",
    "MFCB": "mega-first-corp-bhd",
    "RANHILL": "ranhill-utilities-bhd",
    "PBBANK": "public-bank-bhd",
    "DIGI": "digi-international-bhd",
    "AXIATA": "axiata-group-bhd",
    "MISC": "misc-bhd",
    "PCHEM": "petronas-chemicals-group-bhd",
    "DIALOG": "dialog-group-bhd",
    "IHH": "ihh-healthcare-bhd",
    "HARTA": "hartalega-holdings-bhd",
    "TOPGLOV": "top-glove-corp-bhd",
}


# Investing.com instrument IDs for the fast earnings API
# (endpoints.investing.com/earnings/v1/instruments/{id}/earnings).
# Discovered IDs are cached at runtime; add known IDs here to skip the
# search-API round-trip on the first call.
_INVESTING_INSTRUMENT_IDS: dict[str, int] = {
    "YTL": 41640,
}


@dataclass(frozen=True)
class FeatureTarget:
    """Immutable identifier for a single company / period pair."""

    ticker: str
    fiscal_year: int
    fiscal_quarter: str  # e.g. "Q1", "Q2", "Q3", "Q4"

    @property
    def yf_symbol(self) -> str:
        """Return the yfinance symbol for this KLSE ticker (e.g. '1155.KL')."""
        code = _KLSE_YFINANCE_CODES.get(self.ticker.upper())
        if code:
            return f"{code}.KL"
        return f"{self.ticker}.KL"


@dataclass(frozen=True)
class PeerRef:
    """Identity of a sector peer discovered via TradingView screening."""

    ticker: str
    tv_name: str
    description: str | None
    sector: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "tv_name": self.tv_name,
            "description": self.description,
            "sector": self.sector,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PeerRef":
        return cls(
            ticker=d["ticker"],
            tv_name=d["tv_name"],
            description=d.get("description"),
            sector=d["sector"],
        )


@dataclass
class FeaturePayload:
    """Accumulator passed through all five pipeline phases.

    Each phase appends its metric values to ``metrics`` and any provenance
    information (URLs, timestamps, file paths) to ``source_metadata``.
    Keeping a single mutable object avoids copying large DataFrames between
    phases while still making it obvious which keys each phase owns.
    """

    ticker: str
    fiscal_year: int
    fiscal_quarter: str
    metrics: dict[str, Any] = field(default_factory=dict)
    source_metadata: dict[str, Any] = field(default_factory=dict)

    def set_metric(self, name: str, value: Any) -> None:
        """Set a metric value (None values are preserved for COALESCE UPSERTs)."""
        self.metrics[name] = value

    def set_metadata(self, key: str, value: Any) -> None:
        self.source_metadata[key] = value

    def as_loader_payload(self) -> dict[str, Any]:
        """Flatten into the dict format expected by ``upsert_predictive_features``."""
        return {
            "ticker": self.ticker,
            "fiscal_year": self.fiscal_year,
            "fiscal_quarter": self.fiscal_quarter,
            **self.metrics,
            "source_metadata": json.dumps(self.source_metadata) if self.source_metadata else None,
        }
