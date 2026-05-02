"""Compare extracted database values against ground-truth financial data.

Ground-truth files are JSON documents with a top-level `records` array. Each
record identifies one expected value:

    {
      "ticker": "MAYBANK",
      "fiscal_year": 2024,
      "report_period": "FY",
      "statement": "income_statement",
      "field": "revenue_bln",
      "expected_value": 47.7,
      "tolerance_abs": 0.05
    }

The validator intentionally compares only whitelisted statement/field names so
ground-truth files can be replaced safely without creating arbitrary SQL.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

STATEMENT_FIELDS: dict[str, tuple[str, set[str]]] = {
    "income_statement": (
        "income_statements",
        {
            "revenue_bln",
            "gross_profit_bln",
            "operating_income_bln",
            "net_income_bln",
            "eps",
            "gross_margin_pct",
            "operating_margin_pct",
            "net_margin_pct",
        },
    ),
    "balance_sheet": (
        "balance_sheets",
        {
            "total_assets_bln",
            "total_liabilities_bln",
            "total_equity_bln",
            "cash_and_equivalents_bln",
            "total_debt_bln",
        },
    ),
    "cash_flow": (
        "cash_flows",
        {
            "operating_cash_flow_bln",
            "capital_expenditure_bln",
            "free_cash_flow_bln",
            "dividends_paid_bln",
        },
    ),
    "kpi_summary": (
        "kpi_summaries",
        {
            "revenue_bln",
            "net_income_bln",
            "eps",
            "pe_ratio",
            "roe_pct",
            "roace_pct",
            "debt_to_equity",
            "dividend_yield_pct",
        },
    ),
}


@dataclass(frozen=True)
class GroundTruthRecord:
    ticker: str
    fiscal_year: int
    report_period: str
    statement: str
    field: str
    expected_value: float
    tolerance_abs: float = 0.0


@dataclass
class ValidationResult:
    ticker: str
    fiscal_year: int
    report_period: str
    statement: str
    field: str
    expected_value: float
    actual_value: float | None
    tolerance_abs: float
    passed: bool
    error: str | None = None

    @property
    def absolute_error(self) -> float | None:
        if self.actual_value is None:
            return None
        return abs(self.actual_value - self.expected_value)


def load_ground_truth(path: str | os.PathLike[str]) -> list[GroundTruthRecord]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records = data.get("records", data if isinstance(data, list) else [])
    return [GroundTruthRecord(**record) for record in records]


def compare_value(expected: float, actual: float | None, tolerance_abs: float) -> bool:
    if actual is None:
        return False
    return abs(actual - expected) <= tolerance_abs


def fetch_actual_value(engine: Engine, record: GroundTruthRecord) -> float | None:
    if record.statement not in STATEMENT_FIELDS:
        raise ValueError(f"Unsupported statement: {record.statement}")

    table, allowed_fields = STATEMENT_FIELDS[record.statement]
    if record.field not in allowed_fields:
        raise ValueError(f"Unsupported field for {record.statement}: {record.field}")

    query = text(
        f"SELECT {record.field} FROM {table} "
        "WHERE ticker = :ticker AND fiscal_year = :fiscal_year"
    )
    with engine.connect() as conn:
        row = conn.execute(
            query,
            {"ticker": record.ticker.upper(), "fiscal_year": record.fiscal_year},
        ).first()

    if row is None:
        return None
    value = row[0]
    return None if value is None else float(value)


def validate_records(engine: Engine, records: list[GroundTruthRecord]) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    for record in records:
        try:
            actual = fetch_actual_value(engine, record)
            passed = compare_value(record.expected_value, actual, record.tolerance_abs)
            results.append(
                ValidationResult(
                    ticker=record.ticker.upper(),
                    fiscal_year=record.fiscal_year,
                    report_period=record.report_period,
                    statement=record.statement,
                    field=record.field,
                    expected_value=record.expected_value,
                    actual_value=actual,
                    tolerance_abs=record.tolerance_abs,
                    passed=passed,
                )
            )
        except Exception as exc:
            results.append(
                ValidationResult(
                    ticker=record.ticker.upper(),
                    fiscal_year=record.fiscal_year,
                    report_period=record.report_period,
                    statement=record.statement,
                    field=record.field,
                    expected_value=record.expected_value,
                    actual_value=None,
                    tolerance_abs=record.tolerance_abs,
                    passed=False,
                    error=str(exc),
                )
            )
    return results


def summarize_results(results: list[ValidationResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    failed = total - passed
    missing = sum(1 for result in results if result.actual_value is None)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "missing": missing,
        "accuracy": 0.0 if total == 0 else round(passed / total, 4),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate extracted financial data")
    parser.add_argument(
        "--ground-truth",
        default="ground_truth/mock_ground_truth.json",
        help="Path to ground-truth JSON file",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/finsight"),
        help="SQLAlchemy database URL",
    )
    parser.add_argument("--output", default=None, help="Optional JSON report path")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    engine = create_engine(args.database_url, pool_pre_ping=True)
    records = load_ground_truth(args.ground_truth)
    results = validate_records(engine, records)
    report = {
        "summary": summarize_results(results),
        "results": [
            {
                **asdict(result),
                "absolute_error": result.absolute_error,
            }
            for result in results
        ],
    }

    output = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
