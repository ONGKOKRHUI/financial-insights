"""
Idempotent seed: populates all tables from mock_data if they are empty.
Called on application startup via seed_if_empty().
"""
import json
from sqlalchemy.orm import Session
from models import Company, KPISummary, IncomeStatement, BalanceSheet, CashFlow, QualitativeInsight
from data.mock_data import (
    COMPANIES,
    KPI_SUMMARIES,
    INCOME_STATEMENTS,
    BALANCE_SHEETS,
    CASH_FLOWS,
    QUALITATIVE_INSIGHTS,
)


def seed_if_empty(db: Session) -> None:
    if db.query(Company).first() is not None:
        return

    print("Seeding database from mock data...")

    for ticker, data in COMPANIES.items():
        db.add(Company(**data))
    db.flush()

    for ticker, data in KPI_SUMMARIES.items():
        db.add(KPISummary(**data))

    for ticker, rows in INCOME_STATEMENTS.items():
        for row in rows:
            db.add(IncomeStatement(ticker=ticker, **row))

    for ticker, rows in BALANCE_SHEETS.items():
        for row in rows:
            db.add(BalanceSheet(ticker=ticker, **row))

    for ticker, rows in CASH_FLOWS.items():
        for row in rows:
            db.add(CashFlow(ticker=ticker, **row))

    for ticker, data in QUALITATIVE_INSIGHTS.items():
        db.add(QualitativeInsight(
            ticker=ticker,
            fiscal_year=data["fiscal_year"],
            future_outlook=data["future_outlook"],
            key_strategic_events=json.dumps(data["key_strategic_events"]),
        ))

    db.commit()
    print("Database seeded successfully.")
