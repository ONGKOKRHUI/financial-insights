"""Node: merge_and_validate

Assembles the FinancialReportPayload from both extraction branches.
Validates with Pydantic; on validation error, appends to errors
and returns the partial payload so downstream steps can still run.
"""

import logging

from pydantic import ValidationError

from pipeline.schemas import (
    BalanceSheetSchema,
    CashFlowSchema,
    FinancialReportPayload,
    IncomeStatementSchema,
    KPISummarySchema,
    QualitativeInsightSchema,
)

logger = logging.getLogger(__name__)


def _build_statement(schema_class, ticker: str, fiscal_year: int, raw: dict):
    """Instantiate a schema, injecting ticker and fiscal_year, ignoring missing fields."""
    if not raw:
        return None
    try:
        return schema_class(ticker=ticker, fiscal_year=fiscal_year, **raw)
    except ValidationError as exc:
        logger.warning("Partial validation error for %s: %s", schema_class.__name__, exc)
        # Return what we can by stripping invalid fields
        valid_fields = {k: v for k, v in raw.items() if v is not None}
        try:
            return schema_class(ticker=ticker, fiscal_year=fiscal_year, **valid_fields)
        except ValidationError:
            return None


def merge_and_validate(state: dict) -> dict:
    """LangGraph node: merge quantitative + qualitative → validated FinancialReportPayload."""
    metadata: dict = state.get("metadata", {})
    quantitative_data: dict = state.get("quantitative_data", {})
    qualitative_data: dict = state.get("qualitative_data", {})
    new_errors: list = []

    ticker: str = metadata.get("ticker", "UNKNOWN")
    fiscal_year: int = metadata.get("fiscal_year") or 0
    report_period: str = metadata.get("report_period", "UNKNOWN")
    source_pdf: str = metadata.get("source_pdf", state.get("pdf_path", ""))

    income_statement = _build_statement(
        IncomeStatementSchema, ticker, fiscal_year,
        quantitative_data.get("income_statement", {}),
    )
    balance_sheet = _build_statement(
        BalanceSheetSchema, ticker, fiscal_year,
        quantitative_data.get("balance_sheet", {}),
    )
    cash_flow = _build_statement(
        CashFlowSchema, ticker, fiscal_year,
        quantitative_data.get("cash_flow_statement", {}),
    )
    kpi_summary = _build_statement(
        KPISummarySchema, ticker, fiscal_year,
        quantitative_data.get("kpi_summary", {}),
    )
    qualitative_insight = _build_statement(
        QualitativeInsightSchema, ticker, fiscal_year,
        qualitative_data,
    )

    try:
        payload = FinancialReportPayload(
            ticker=ticker,
            fiscal_year=fiscal_year,
            report_period=report_period,
            source_pdf=source_pdf,
            income_statement=income_statement,
            balance_sheet=balance_sheet,
            cash_flow=cash_flow,
            qualitative_insight=qualitative_insight,
            kpi_summary=kpi_summary,
        )
        validated_payload = payload.model_dump()
        logger.info("Payload validated for %s FY%s", ticker, fiscal_year)
    except ValidationError as exc:
        new_errors.append(f"Final payload validation failed: {exc}")
        logger.error("Final validation error: %s", exc)
        validated_payload = {
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "report_period": report_period,
            "source_pdf": source_pdf,
        }

    return {
        "validated_payload": validated_payload,
        "errors": new_errors,
    }
