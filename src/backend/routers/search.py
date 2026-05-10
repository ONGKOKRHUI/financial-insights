import json
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user, require_api_key_or_session
from database import get_db
from models import (
    BalanceSheet,
    CashFlow,
    Company,
    IncomeStatement,
    KPISummary,
    QualitativeInsight,
    User,
)

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)

StatementType = Literal[
    "income_statement",
    "balance_sheet",
    "cash_flow",
    "kpi",
    "qualitative",
]

# ---------------------------------------------------------------------------
# Live search models
# ---------------------------------------------------------------------------


class LiveSearchHit(BaseModel):
    rank: int
    title: str
    snippet: str
    source_path: str
    source_uri: Optional[str]
    score: float
    doc_type: str
    domain: str
    ticker: Optional[str]


class LiveSearchResponse(BaseModel):
    query: str
    hits: list[LiveSearchHit]
    total: int


# ---------------------------------------------------------------------------
# Structured financial search models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    ticker: str
    statement_type: StatementType
    fiscal_year: Optional[int] = None


class SearchResponse(BaseModel):
    ticker: str
    statement_type: str
    fiscal_year: Optional[int]
    data: dict


@router.get(
    "/live",
    response_model=LiveSearchResponse,
    summary="Live (search-as-you-type) Elasticsearch suggestions",
    description=(
        "Returns the top 5 most relevant docs/page suggestions for a partial query string "
        "using edge n-gram BM25 search over the indexed webpage content.  "
        "Results are lightweight (title, snippet, path) and ordered by relevance score.  "
        "Requires a valid session cookie or X-API-Key header."
    ),
)
def live_search_endpoint(
    q: str = Query(..., min_length=2, max_length=200, description="Partial search query (min 2 chars)"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> LiveSearchResponse:
    """Search-as-you-type endpoint backed by Elasticsearch + company DB lookup."""
    stripped = q.strip()
    if len(stripped) < 2:
        return LiveSearchResponse(query=stripped, hits=[], total=0)

    # ── Company hits from PostgreSQL ────────────────────────────────────────
    company_rows = (
        db.query(Company)
        .filter(
            or_(
                Company.ticker.ilike(f"%{stripped}%"),
                Company.name.ilike(f"%{stripped}%"),
            )
        )
        .limit(3)
        .all()
    )
    company_hits = [
        LiveSearchHit(
            rank=0,  # re-ranked below
            title=c.name,
            snippet=f"{c.sector} · {c.exchange} · {c.currency} · {c.headquarters}",
            source_path=f"companies/{c.ticker}",
            source_uri=f"/companies/{c.ticker}",
            score=100.0,  # always surfaces above doc hits
            doc_type="company_profile",
            domain="company",
            ticker=c.ticker,
        )
        for c in company_rows
    ]

    # ── Doc hits from Elasticsearch ─────────────────────────────────────────
    doc_hits: list[LiveSearchHit] = []
    try:
        from services.live_search import live_search

        remaining = max(0, 5 - len(company_hits))
        if remaining > 0:
            raw = live_search(stripped, top_k=remaining)
            doc_hits = [
                LiveSearchHit(
                    rank=0,
                    title=h.title,
                    snippet=h.snippet,
                    source_path=h.source_path,
                    source_uri=h.source_uri,
                    score=h.score,
                    doc_type=h.doc_type,
                    domain=h.domain,
                    ticker=h.ticker,
                )
                for h in raw
            ]
    except Exception as exc:
        logger.warning("live_search ES failed for query %r: %s", stripped, exc)

    # ── Merge, cap at 5, assign ranks ───────────────────────────────────────
    merged = (company_hits + doc_hits)[:5]
    for i, hit in enumerate(merged, start=1):
        hit.rank = i

    return LiveSearchResponse(query=stripped, hits=merged, total=len(merged))


@router.post("", response_model=SearchResponse, summary="Unified financial data query")
def search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_api_key_or_session),
):
    """
    Unified payload-based query endpoint.

    Send `ticker`, `statement_type`, and an optional `fiscal_year` to
    retrieve any financial record from a single endpoint.  Omit
    `fiscal_year` to receive the most recent available year.

    **statement_type** must be one of:
    `income_statement` | `balance_sheet` | `cash_flow` | `kpi` | `qualitative`
    """
    key = payload.ticker.upper()
    fy = payload.fiscal_year
    st = payload.statement_type

    company = db.query(Company).filter(Company.ticker == key).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{key}' not found.")

    if st == "income_statement":
        q = db.query(IncomeStatement).filter(IncomeStatement.ticker == key)
        q = q.filter(IncomeStatement.fiscal_year == fy) if fy else q.order_by(IncomeStatement.fiscal_year.desc())
        row = q.first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Income statement for '{key}' not found.")
        return SearchResponse(
            ticker=key,
            statement_type=st,
            fiscal_year=row.fiscal_year,
            data={
                "fiscal_year": row.fiscal_year,
                "revenue_bln": row.revenue_bln,
                "gross_profit_bln": row.gross_profit_bln,
                "operating_income_bln": row.operating_income_bln,
                "net_income_bln": row.net_income_bln,
                "eps": row.eps,
                "gross_margin_pct": row.gross_margin_pct,
                "operating_margin_pct": row.operating_margin_pct,
                "net_margin_pct": row.net_margin_pct,
            },
        )

    if st == "balance_sheet":
        q = db.query(BalanceSheet).filter(BalanceSheet.ticker == key)
        q = q.filter(BalanceSheet.fiscal_year == fy) if fy else q.order_by(BalanceSheet.fiscal_year.desc())
        row = q.first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Balance sheet for '{key}' not found.")
        return SearchResponse(
            ticker=key,
            statement_type=st,
            fiscal_year=row.fiscal_year,
            data={
                "fiscal_year": row.fiscal_year,
                "total_assets_bln": row.total_assets_bln,
                "total_liabilities_bln": row.total_liabilities_bln,
                "total_equity_bln": row.total_equity_bln,
                "cash_and_equivalents_bln": row.cash_and_equivalents_bln,
                "total_debt_bln": row.total_debt_bln,
            },
        )

    if st == "cash_flow":
        q = db.query(CashFlow).filter(CashFlow.ticker == key)
        q = q.filter(CashFlow.fiscal_year == fy) if fy else q.order_by(CashFlow.fiscal_year.desc())
        row = q.first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Cash flow for '{key}' not found.")
        return SearchResponse(
            ticker=key,
            statement_type=st,
            fiscal_year=row.fiscal_year,
            data={
                "fiscal_year": row.fiscal_year,
                "operating_cash_flow_bln": row.operating_cash_flow_bln,
                "capital_expenditure_bln": row.capital_expenditure_bln,
                "free_cash_flow_bln": row.free_cash_flow_bln,
                "dividends_paid_bln": row.dividends_paid_bln,
            },
        )

    if st == "kpi":
        q = db.query(KPISummary).filter(KPISummary.ticker == key)
        q = q.filter(KPISummary.fiscal_year == fy) if fy else q.order_by(KPISummary.fiscal_year.desc())
        row = q.first()
        if not row:
            raise HTTPException(status_code=404, detail=f"KPI summary for '{key}' not found.")
        return SearchResponse(
            ticker=key,
            statement_type=st,
            fiscal_year=row.fiscal_year,
            data={
                "fiscal_year": row.fiscal_year,
                "revenue_bln": row.revenue_bln,
                "net_income_bln": row.net_income_bln,
                "eps": row.eps,
                "pe_ratio": row.pe_ratio,
                "roe_pct": row.roe_pct,
                "roace_pct": row.roace_pct,
                "debt_to_equity": row.debt_to_equity,
                "dividend_yield_pct": row.dividend_yield_pct,
            },
        )

    # st == "qualitative"
    q = db.query(QualitativeInsight).filter(QualitativeInsight.ticker == key)
    q = q.filter(QualitativeInsight.fiscal_year == fy) if fy else q.order_by(QualitativeInsight.fiscal_year.desc())
    row = q.first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Qualitative insight for '{key}' not found.")
    return SearchResponse(
        ticker=key,
        statement_type=st,
        fiscal_year=row.fiscal_year,
        data={
            "fiscal_year": row.fiscal_year,
            "future_outlook": row.future_outlook,
            "key_strategic_events": json.loads(row.key_strategic_events),
        },
    )
