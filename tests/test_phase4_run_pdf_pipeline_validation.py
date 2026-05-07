"""Manual runner: process selected PDFs and validate against ground truth.

How to use:
1) Set either SINGLE_PDF_PATH or PDF_PATHS in the config section below.
2) Run:
      PYTHONPATH=src python tests/run_pdf_pipeline_validation.py
      

This script will:
- run the full extraction pipeline per PDF (`pipeline.graph.run_pipeline`)
- upsert the extracted payload into Postgres (`db.loader.upsert_report`)
- mark run status in `pipeline_runs`
- validate DB values against `ground_truth/mock_ground_truth.json`
  for the exact ticker/fiscal_year pairs extracted from selected PDFs

PDF paths you can try now with your current ground_truth/mock_ground_truth.json (FY2025):
"""

# C:\Users\HP\Documents\repos\financial-insights\src\scraper\data\raw\MAYBANK\MAYBANK_2025_Q4.pdf
# C:\Users\HP\Documents\repos\financial-insights\src\scraper\data\raw\CIMB\CIMB_2025_Q4.pdf
# C:\Users\HP\Documents\repos\financial-insights\src\scraper\data\raw\TNB\TNB_2025_Q4.pdf
# C:\Users\HP\Documents\repos\financial-insights\src\scraper\data\raw\PETRONAS\PETRONAS_2025_Q4.pdf
# C:\Users\HP\Documents\repos\financial-insights\src\scraper\data\raw\MAXIS\MAXIS_2025_Q4.pdf
# C:\Users\HP\Documents\repos\financial-insights\src\scraper\data\raw\TELEKOM\TELEKOM_2025_Q4.pdf
# C:\Users\HP\Documents\repos\financial-insights\src\scraper\data\raw\GENTING\GENTING_2025_Q4.pdf
# C:\Users\HP\Documents\repos\financial-insights\src\scraper\data\raw\SUNWAY\SUNWAY_2025_Q4.pdf

# Use this interpreter:
    # .\venv\Scripts\python.exe tests/test_phase4_run_pdf_pipeline_validation.py
# Not this one:
    # C:\Users\HP\AppData\Local\Programs\Python\Python313\python.exe ...


from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Ensure src imports work when executed from repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
BACKEND_DIR = SRC_DIR / "backend"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db.loader import mark_processed, upsert_report
from data.mock_data import COMPANIES as MOCK_COMPANIES
from pipeline.graph import run_pipeline
from validation.validate_extraction_accuracy import (
    ValidationResult,
    load_ground_truth,
    summarize_results,
    validate_records,
)


# ===============================
# Config (edit these values)
# ===============================
# Option A: run exactly one PDF.
SINGLE_PDF_PATH: str | None = None

# Option B: run multiple PDFs.
PDF_PATHS: list[str] = [
    r"src/scraper/data/raw/MAYBANK/MAYBANK_2025_Q4.pdf",
    r"src/scraper/data/raw/CIMB/CIMB_2025_Q4.pdf",
    r"src/scraper/data/raw/TNB/TNB_2025_Q4.pdf",
    r"src/scraper/data/raw/PETRONAS/PETRONAS_2025_Q4.pdf",
    r"src/scraper/data/raw/MAXIS/MAXIS_2025_Q4.pdf",
    r"src/scraper/data/raw/TELEKOM/TELEKOM_2025_Q4.pdf",
    r"src/scraper/data/raw/GENTING/GENTING_2025_Q4.pdf",
    r"src/scraper/data/raw/SUNWAY/SUNWAY_2025_Q4.pdf",
]

# Optional: skip problematic tickers or explicit PDF paths.
SKIP_TICKERS: set[str] = set()
SKIP_PDF_PATHS: set[str] = set()
MAX_PDFS: int | None = 1

# Ground-truth file used for validation.
# mock "ground_truth/mock_ground_truth.json"
# ground truth "ground_truth/ground_truth.json"
GROUND_TRUTH_PATH = "ground_truth/ground_truth.json"

# Optional output file for detailed result JSON.
OUTPUT_REPORT_PATH = "tests/manual_pdf_validation_report.json"

# Optional explicit DB URL override. Leave as None to auto-select.
DATABASE_URL_OVERRIDE: str | None = None
LOCAL_FALLBACK_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/finsight"

_ACTIVE_DATABASE_URL: str | None = None


@dataclass
class PipelineRunResult:
    pdf_path: str
    status: str
    ticker: str | None = None
    fiscal_year: int | None = None
    errors: list[str] | None = None


def _normalize_path_for_compare(path: Path | str) -> str:
    return str(Path(path).resolve()).lower()


def _resolve_pdf_paths() -> list[Path]:
    env_single_pdf = os.getenv("FINSIGHT_TEST_SINGLE_PDF")
    env_max_pdfs = os.getenv("FINSIGHT_TEST_MAX_PDFS")

    configured = []
    if env_single_pdf:
        configured.append(env_single_pdf)
    elif SINGLE_PDF_PATH:
        configured.append(SINGLE_PDF_PATH)
    configured.extend(PDF_PATHS)

    if not configured:
        raise ValueError(
            "No PDFs configured. Set SINGLE_PDF_PATH or add entries to PDF_PATHS."
        )

    resolved: list[Path] = []
    for p in configured:
        candidate = Path(p)
        if not candidate.is_absolute():
            candidate = (REPO_ROOT / candidate).resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Configured PDF does not exist: {candidate}")
        ticker = candidate.stem.split("_", 1)[0].upper()
        if ticker in {t.upper() for t in SKIP_TICKERS}:
            continue
        if _normalize_path_for_compare(candidate) in {
            _normalize_path_for_compare(p) for p in SKIP_PDF_PATHS
        }:
            continue
        resolved.append(candidate)
    max_pdfs = MAX_PDFS
    if env_max_pdfs:
        try:
            max_pdfs = int(env_max_pdfs)
        except ValueError:
            pass
    if max_pdfs is not None and max_pdfs > 0:
        return resolved[:max_pdfs]
    return resolved


def _ensure_company_exists(ticker: str) -> None:
    """Insert a minimal companies row if missing (helps FK integrity in manual runs)."""
    data = MOCK_COMPANIES.get(ticker.upper())
    if not data:
        return

    database_url = _ACTIVE_DATABASE_URL or os.getenv("DATABASE_URL", LOCAL_FALLBACK_DATABASE_URL)
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM companies WHERE ticker = :ticker"),
            {"ticker": ticker.upper()},
        ).first()
        if exists:
            return

        conn.execute(
            text(
                """
                INSERT INTO companies
                (ticker, name, sector, industry, description, market_cap_bln, employees, founded, headquarters, website, currency, exchange)
                VALUES
                (:ticker, :name, :sector, :industry, :description, :market_cap_bln, :employees, :founded, :headquarters, :website, :currency, :exchange)
                """
            ),
            {
                "ticker": data.get("ticker"),
                "name": data.get("name"),
                "sector": data.get("sector"),
                "industry": data.get("industry"),
                "description": data.get("description"),
                "market_cap_bln": data.get("market_cap_bln"),
                "employees": data.get("employees"),
                "founded": data.get("founded"),
                "headquarters": data.get("headquarters"),
                "website": data.get("website"),
                "currency": data.get("currency"),
                "exchange": data.get("exchange"),
            },
        )


def _run_and_upsert(pdf_path: Path) -> PipelineRunResult:
    try:
        mark_processed(str(pdf_path), status="processing")
    except Exception:
        # Continue even when pipeline_runs tracking DB is unavailable.
        pass
    try:
        result = run_pipeline(str(pdf_path))
        payload = result.get("validated_payload") or {}
        errors = list(result.get("errors") or [])

        ticker = payload.get("ticker")
        fiscal_year = payload.get("fiscal_year")
        if not ticker or not fiscal_year:
            raise ValueError(
                f"Pipeline returned empty/invalid payload for {pdf_path}. Errors: {errors}"
            )

        _ensure_company_exists(str(ticker))
        upsert_report(payload)
        mark_processed(
            str(pdf_path),
            status="success",
            ticker=str(ticker),
            fiscal_year=int(fiscal_year),
        )
        return PipelineRunResult(
            pdf_path=str(pdf_path),
            status="success",
            ticker=str(ticker).upper(),
            fiscal_year=int(fiscal_year),
            errors=errors,
        )
    except Exception as exc:  # pragma: no cover - manual script
        try:
            mark_processed(str(pdf_path), status="error", error_msg=str(exc))
        except Exception:
            pass
        return PipelineRunResult(
            pdf_path=str(pdf_path),
            status="error",
            errors=[str(exc)],
        )


def _filter_ground_truth(records: list[Any], successful: list[PipelineRunResult]) -> list[Any]:
    pairs = {(r.ticker, r.fiscal_year) for r in successful if r.ticker and r.fiscal_year}
    return [
        record
        for record in records
        if (record.ticker.upper(), record.fiscal_year) in pairs
        and record.expected_value is not None
    ]


def _print_results(
    run_results: list[PipelineRunResult],
    validation_results: list[ValidationResult],
) -> None:
    print("\n=== PIPELINE RUN RESULTS ===")
    for item in run_results:
        print(
            f"- {item.status.upper():7} | {item.pdf_path}"
            f" | ticker={item.ticker} fy={item.fiscal_year}"
        )
        if item.errors:
            print(f"  errors: {item.errors}")

    print("\n=== VALIDATION SUMMARY ===")
    summary = summarize_results(validation_results)
    print(json.dumps(summary, indent=2))

    failed = [r for r in validation_results if not r.passed]
    if failed:
        print("\n=== FAILED / MISSING FIELDS ===")
        for r in failed:
            print(
                f"- {r.ticker} FY{r.fiscal_year} {r.statement}.{r.field}"
                f" expected={r.expected_value} actual={r.actual_value}"
                f" tolerance={r.tolerance_abs} error={r.error}"
            )
    else:
        print("\nAll validated fields passed within tolerance.")


def _print_run_results_only(run_results: list[PipelineRunResult]) -> None:
    print("\n=== PIPELINE RUN RESULTS ===")
    for item in run_results:
        print(
            f"- {item.status.upper():7} | {item.pdf_path}"
            f" | ticker={item.ticker} fy={item.fiscal_year}"
        )
        if item.errors:
            print(f"  errors: {item.errors}")


def _print_company_summary(run_results: list[PipelineRunResult]) -> None:
    counts: dict[str, dict[str, int]] = {}
    for item in run_results:
        label = item.ticker or Path(item.pdf_path).stem.split("_", 1)[0].upper()
        counts.setdefault(label, {"success": 0, "error": 0})
        counts[label][item.status] = counts[label].get(item.status, 0) + 1

    print("\n=== PER-TICKER RUN SUMMARY ===")
    for ticker in sorted(counts):
        print(
            f"- {ticker}: success={counts[ticker].get('success', 0)} "
            f"error={counts[ticker].get('error', 0)}"
        )


def main() -> None:
    global _ACTIVE_DATABASE_URL
    candidates = []
    if DATABASE_URL_OVERRIDE:
        candidates.append(DATABASE_URL_OVERRIDE)
    env_database_url = os.getenv("DATABASE_URL")
    if env_database_url:
        candidates.append(env_database_url)
    candidates.append(LOCAL_FALLBACK_DATABASE_URL)

    resolved_db_url = None
    for candidate in dict.fromkeys(candidates):
        try:
            engine = create_engine(candidate, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            resolved_db_url = candidate
            break
        except OperationalError:
            continue

    if not resolved_db_url:
        raise RuntimeError(
            "No reachable PostgreSQL database. Set DATABASE_URL_OVERRIDE (or DATABASE_URL) "
            "to a working connection string, or start local Postgres via docker compose."
        )

    _ACTIVE_DATABASE_URL = resolved_db_url
    os.environ["DATABASE_URL"] = resolved_db_url

    pdf_paths = _resolve_pdf_paths()

    run_results = [_run_and_upsert(path) for path in pdf_paths]
    successful = [r for r in run_results if r.status == "success" and r.ticker and r.fiscal_year]
    if not successful:
        _print_run_results_only(run_results)
        _print_company_summary(run_results)
        raise RuntimeError("No successful pipeline runs; skipping validation.")

    ground_truth_records = load_ground_truth(GROUND_TRUTH_PATH)
    scoped_records = _filter_ground_truth(ground_truth_records, successful)
    if not scoped_records:
        _print_run_results_only(run_results)
        _print_company_summary(run_results)
        raise RuntimeError(
            "No ground-truth records matched extracted ticker/fiscal_year pairs. "
            f"Pairs found: {sorted({(r.ticker, r.fiscal_year) for r in successful})}"
        )

    database_url = _ACTIVE_DATABASE_URL or os.getenv("DATABASE_URL", LOCAL_FALLBACK_DATABASE_URL)
    engine = create_engine(database_url, pool_pre_ping=True)
    validation_results = validate_records(engine, scoped_records)

    report = {
        "configured_pdf_paths": [str(p) for p in pdf_paths],
        "pipeline_results": [asdict(x) for x in run_results],
        "validated_ticker_year_pairs": sorted({(r.ticker, r.fiscal_year) for r in successful}),
        "summary": summarize_results(validation_results),
        "results": [
            {
                **asdict(result),
                "absolute_error": result.absolute_error,
            }
            for result in validation_results
        ],
    }
    (REPO_ROOT / OUTPUT_REPORT_PATH).write_text(json.dumps(report, indent=2), encoding="utf-8")

    _print_results(run_results, validation_results)
    _print_company_summary(run_results)
    print(f"\nDetailed report saved to: {REPO_ROOT / OUTPUT_REPORT_PATH}")


if __name__ == "__main__":
    main()
