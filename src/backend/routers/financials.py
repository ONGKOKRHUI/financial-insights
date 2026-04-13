from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Company, IncomeStatement, BalanceSheet, CashFlow
from schemas import (
    IncomeStatementEntry,
    IncomeStatementResponse,
    BalanceSheetEntry,
    BalanceSheetResponse,
    CashFlowEntry,
    CashFlowResponse,
)

router = APIRouter(prefix="/financials", tags=["financials"])


def _get_company_or_404(ticker: str, db: Session) -> Company:
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found.")
    return company


@router.get("/{ticker}/income-statement", response_model=IncomeStatementResponse)
def get_income_statement(ticker: str, db: Session = Depends(get_db)):
    """Return annual income statement history for a company."""
    key = ticker.upper()
    company = _get_company_or_404(key, db)
    rows = (
        db.query(IncomeStatement)
        .filter(IncomeStatement.ticker == key)
        .order_by(IncomeStatement.fiscal_year)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Income statement for '{ticker}' not found.")
    return IncomeStatementResponse(
        ticker=key,
        name=company.name,
        currency=company.currency,
        data=[
            IncomeStatementEntry(
                fiscal_year=r.fiscal_year,
                revenue_bln=r.revenue_bln,
                gross_profit_bln=r.gross_profit_bln,
                operating_income_bln=r.operating_income_bln,
                net_income_bln=r.net_income_bln,
                eps=r.eps,
                gross_margin_pct=r.gross_margin_pct,
                operating_margin_pct=r.operating_margin_pct,
                net_margin_pct=r.net_margin_pct,
            )
            for r in rows
        ],
    )


@router.get("/{ticker}/balance-sheet", response_model=BalanceSheetResponse)
def get_balance_sheet(ticker: str, db: Session = Depends(get_db)):
    """Return annual balance sheet history for a company."""
    key = ticker.upper()
    company = _get_company_or_404(key, db)
    rows = (
        db.query(BalanceSheet)
        .filter(BalanceSheet.ticker == key)
        .order_by(BalanceSheet.fiscal_year)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Balance sheet for '{ticker}' not found.")
    return BalanceSheetResponse(
        ticker=key,
        name=company.name,
        currency=company.currency,
        data=[
            BalanceSheetEntry(
                fiscal_year=r.fiscal_year,
                total_assets_bln=r.total_assets_bln,
                total_liabilities_bln=r.total_liabilities_bln,
                total_equity_bln=r.total_equity_bln,
                cash_and_equivalents_bln=r.cash_and_equivalents_bln,
                total_debt_bln=r.total_debt_bln,
            )
            for r in rows
        ],
    )


@router.get("/{ticker}/cash-flow", response_model=CashFlowResponse)
def get_cash_flow(ticker: str, db: Session = Depends(get_db)):
    """Return annual cash flow history for a company."""
    key = ticker.upper()
    company = _get_company_or_404(key, db)
    rows = (
        db.query(CashFlow)
        .filter(CashFlow.ticker == key)
        .order_by(CashFlow.fiscal_year)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Cash flow for '{ticker}' not found.")
    return CashFlowResponse(
        ticker=key,
        name=company.name,
        currency=company.currency,
        data=[
            CashFlowEntry(
                fiscal_year=r.fiscal_year,
                operating_cash_flow_bln=r.operating_cash_flow_bln,
                capital_expenditure_bln=r.capital_expenditure_bln,
                free_cash_flow_bln=r.free_cash_flow_bln,
                dividends_paid_bln=r.dividends_paid_bln,
            )
            for r in rows
        ],
    )
