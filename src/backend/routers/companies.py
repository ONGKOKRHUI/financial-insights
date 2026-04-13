import json
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Company, KPISummary as KPISummaryModel, QualitativeInsight as QualitativeInsightModel
from schemas import CompanySummary, CompanyDetail, KPISummary, QualitativeInsight

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanySummary])
def list_companies(db: Session = Depends(get_db)):
    """Return a summary list of all available companies."""
    companies = db.query(Company).all()
    return [
        CompanySummary(
            ticker=c.ticker,
            name=c.name,
            sector=c.sector,
            market_cap_bln=c.market_cap_bln,
            currency=c.currency,
        )
        for c in companies
    ]


@router.get("/{ticker}", response_model=CompanyDetail)
def get_company(ticker: str, db: Session = Depends(get_db)):
    """Return full detail for a single company by ticker symbol."""
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found.")
    return CompanyDetail(
        ticker=company.ticker,
        name=company.name,
        sector=company.sector,
        industry=company.industry,
        description=company.description,
        market_cap_bln=company.market_cap_bln,
        employees=company.employees,
        founded=company.founded,
        headquarters=company.headquarters,
        website=company.website,
        currency=company.currency,
        exchange=company.exchange,
    )


@router.get("/{ticker}/summary", response_model=KPISummary)
def get_company_summary(ticker: str, db: Session = Depends(get_db)):
    """Return the latest KPI summary for a company."""
    key = ticker.upper()
    row = (
        db.query(KPISummaryModel)
        .filter(KPISummaryModel.ticker == key)
        .order_by(KPISummaryModel.fiscal_year.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"KPI summary for '{ticker}' not found.")
    return KPISummary(
        ticker=row.ticker,
        revenue_bln=row.revenue_bln,
        net_income_bln=row.net_income_bln,
        eps=row.eps,
        pe_ratio=row.pe_ratio,
        roe_pct=row.roe_pct,
        roace_pct=row.roace_pct,
        debt_to_equity=row.debt_to_equity,
        dividend_yield_pct=row.dividend_yield_pct,
        fiscal_year=row.fiscal_year,
    )


@router.get("/{ticker}/qualitative", response_model=QualitativeInsight)
def get_qualitative_insight(ticker: str, db: Session = Depends(get_db)):
    """Return the latest qualitative insight for a company."""
    key = ticker.upper()
    row = (
        db.query(QualitativeInsightModel)
        .filter(QualitativeInsightModel.ticker == key)
        .order_by(QualitativeInsightModel.fiscal_year.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Qualitative insight for '{ticker}' not found.")
    return QualitativeInsight(
        ticker=row.ticker,
        fiscal_year=row.fiscal_year,
        future_outlook=row.future_outlook,
        key_strategic_events=json.loads(row.key_strategic_events),
    )
