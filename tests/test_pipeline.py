"""FinSight ETL Pipeline — Test Suite

Tests are organised in three tiers:

  Tier 1 — Import smoke tests (no DB, no LLM, no PDF required)
  Tier 2 — Schema & logic unit tests (no external services)
  Tier 3 — Integration test (requires .env, running DB, and a real PDF)

Run all:
    python tests/test_pipeline.py

Run only smoke tests (CI-safe):
    python tests/test_pipeline.py --smoke

Run integration test with a specific PDF:
    python tests/test_pipeline.py --integration --pdf path/to/report.pdf
"""

import argparse
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

# ── PYTHONPATH bootstrap ───────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

_PASSED = 0
_FAILED = 0


def _pass(label: str) -> None:
    global _PASSED
    _PASSED += 1
    print(f"  {GREEN}✓{RESET} {label}")


def _fail(label: str, reason: str = "") -> None:
    global _FAILED
    _FAILED += 1
    suffix = f" — {reason}" if reason else ""
    print(f"  {RED}✗{RESET} {label}{suffix}")


def _section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")
    print("  " + "─" * (len(title) + 2))


# ══════════════════════════════════════════════════════════════════════════════
# Tier 1 — Import smoke tests
# ══════════════════════════════════════════════════════════════════════════════

def test_imports() -> None:
    _section("Tier 1 — Import smoke tests")

    modules = [
        ("pipeline.state",               "PipelineState"),
        ("pipeline.schemas",             "FinancialReportPayload"),
        ("pipeline.nodes.parser",        "parse_pdf"),
        ("pipeline.nodes.router",        "route_content"),
        ("pipeline.nodes.quantitative",  "extract_quantitative"),
        ("pipeline.nodes.qualitative",   "extract_qualitative"),
        ("pipeline.nodes.merger",        "merge_and_validate"),
        ("pipeline.dify_client",         "run_dify_workflow"),
        ("db.loader",                    "upsert_report"),
    ]

    for module_name, symbol in modules:
        try:
            mod = __import__(module_name, fromlist=[symbol])
            assert hasattr(mod, symbol), f"{symbol} not found in {module_name}"
            _pass(f"import {module_name}.{symbol}")
        except Exception as exc:
            _fail(f"import {module_name}.{symbol}", str(exc))

    # LangGraph graph construction (does NOT require LLM credentials)
    try:
        # We patch env vars to prevent missing-key crashes during graph build
        os.environ.setdefault("GOOGLE_API_KEY", "dummy-for-test")
        from pipeline.graph import build_graph
        graph = build_graph()
        assert graph is not None
        _pass("pipeline.graph.build_graph() — LangGraph compiled OK")
    except Exception as exc:
        _fail("pipeline.graph.build_graph()", str(exc))

    # DAG import test — only runs when apache-airflow is installed (e.g. inside Docker)
    try:
        import airflow  # noqa: F401
        _dag_path = str(_REPO_ROOT / "dags")
        if _dag_path not in sys.path:
            sys.path.insert(0, _dag_path)
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "finsight_etl_dag",
            str(_REPO_ROOT / "dags" / "finsight_etl_dag.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "dag")
        _pass("dags/finsight_etl_dag.py — Airflow DAG imported OK")
    except ImportError:
        global _PASSED
        _PASSED += 1
        print(f"  \033[93m~\033[0m dags/finsight_etl_dag.py — skipped (apache-airflow not installed locally; runs in Docker)")
    except Exception as exc:
        _fail("dags/finsight_etl_dag.py import", str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# Tier 2 — Schema & logic unit tests
# ══════════════════════════════════════════════════════════════════════════════

def test_schemas() -> None:
    _section("Tier 2 — Schema & logic unit tests")

    # --- FinancialReportPayload: valid payload
    try:
        from pipeline.schemas import FinancialReportPayload, IncomeStatementSchema

        payload = FinancialReportPayload(
            ticker="MAYBANK",
            fiscal_year=2024,
            report_period="Q3",
            source_pdf="/tmp/MAYBANK_2024_Q3.pdf",
            income_statement=IncomeStatementSchema(
                ticker="MAYBANK",
                fiscal_year=2024,
                revenue_bln=12.5,
                net_income_bln=2.3,
                eps=0.22,
            ),
        )
        assert payload.ticker == "MAYBANK"
        assert payload.income_statement.revenue_bln == 12.5
        _pass("FinancialReportPayload — valid construction")
    except Exception as exc:
        _fail("FinancialReportPayload valid", str(exc))

    # --- FinancialReportPayload: optional fields nullable
    try:
        from pipeline.schemas import FinancialReportPayload

        payload = FinancialReportPayload(
            ticker="TNB",
            fiscal_year=2023,
            report_period="ANNUAL",
            source_pdf="/tmp/TNB_2023_ANNUAL.pdf",
        )
        assert payload.income_statement is None
        _pass("FinancialReportPayload — optional fields nullable")
    except Exception as exc:
        _fail("FinancialReportPayload optional", str(exc))

    # --- metadata extraction from filename
    try:
        from pipeline.nodes.parser import _extract_metadata_from_path

        meta = _extract_metadata_from_path("/some/path/MAYBANK_2024_Q3.pdf")
        assert meta["ticker"] == "MAYBANK"
        assert meta["fiscal_year"] == 2024
        assert meta["report_period"] == "Q3"
        _pass("_extract_metadata_from_path — standard filename")

        meta2 = _extract_metadata_from_path("/some/path/CIMB_2023_Q4.pdf")
        assert meta2["ticker"] == "CIMB"
        assert meta2["fiscal_year"] == 2023
        _pass("_extract_metadata_from_path — CIMB Q4")
    except Exception as exc:
        _fail("_extract_metadata_from_path", str(exc))

    # --- router: regex split does not crash on empty input
    try:
        from pipeline.nodes.router import route_content

        state = {"markdown_text": "", "errors": []}
        result = route_content(state)
        assert "table_markdown" in result
        assert "narrative_markdown" in result
        _pass("route_content — empty input handled gracefully")
    except Exception as exc:
        _fail("route_content empty input", str(exc))

    # --- router: splits a realistic markdown sample
    try:
        from pipeline.nodes.router import route_content

        sample_md = (
            "## Management Discussion\n\nThe group recorded strong performance...\n\n"
            "## Income Statement\n\n"
            "| Item           | 2024    | 2023    |\n"
            "| Revenue        | 12,500  | 11,200  |\n"
            "| Net Income     |  2,300  |  2,100  |\n\n"
            "## Outlook\n\nWe remain cautiously optimistic...\n"
        )
        state = {"markdown_text": sample_md, "errors": []}
        result = route_content(state)
        assert len(result["table_markdown"]) > 0
        assert len(result["narrative_markdown"]) > 0
        _pass("route_content — realistic markdown split")
    except Exception as exc:
        _fail("route_content markdown split", str(exc))

    # --- merger: assembles payload correctly
    try:
        from pipeline.nodes.merger import merge_and_validate

        state = {
            "pdf_path": "/tmp/MAYBANK_2024_Q3.pdf",
            "metadata": {"ticker": "MAYBANK", "fiscal_year": 2024, "report_period": "Q3", "source_pdf": "/tmp/MAYBANK_2024_Q3.pdf"},
            "quantitative_data": {
                "income_statement": {"revenue_bln": 12.5, "net_income_bln": 2.3, "eps": 0.22},
                "balance_sheet": {"total_assets_bln": 100.0, "total_equity_bln": 20.0},
                "cash_flow_statement": {"operating_cash_flow_bln": 3.1},
                "kpi_summary": {"roe_pct": 11.5, "debt_to_equity": 0.8},
            },
            "qualitative_data": {
                "future_outlook": "Cautiously optimistic for FY2025.",
                "key_strategic_events": '["Digital banking expansion", "Overseas acquisition"]',
            },
            "errors": [],
        }
        result = merge_and_validate(state)
        assert result["validated_payload"]["ticker"] == "MAYBANK"
        assert result["validated_payload"]["fiscal_year"] == 2024
        _pass("merge_and_validate — assembles payload from both branches")
    except Exception as exc:
        _fail("merge_and_validate", str(exc))

    # --- loader: upsert_report raises ValueError on bad payload
    try:
        from db.loader import upsert_report

        try:
            upsert_report({"ticker": "", "fiscal_year": 0})
            _fail("upsert_report — should raise ValueError on empty ticker/year")
        except ValueError:
            _pass("upsert_report — raises ValueError on empty ticker/fiscal_year")
    except Exception as exc:
        _fail("upsert_report ValueError guard", str(exc))


# ══════════════════════════════════════════════════════════════════════════════
# Tier 3 — Integration test (real DB + real PDF)
# ══════════════════════════════════════════════════════════════════════════════

def test_integration(pdf_path: str) -> None:
    _section(f"Tier 3 — Integration test\n  PDF: {pdf_path}")

    if not os.path.isfile(pdf_path):
        _fail("PDF file exists", f"Not found: {pdf_path}")
        return

    _pass(f"PDF file found ({os.path.getsize(pdf_path):,} bytes)")

    # Step 1: Run the pipeline
    try:
        from pipeline.graph import run_pipeline

        print(f"  {YELLOW}→ Running pipeline (this may take 30–90 s) …{RESET}")
        result = run_pipeline(pdf_path)

        payload = result.get("validated_payload", {})
        errors = result.get("errors", [])
        metadata = result.get("metadata", {})

        _pass(f"pipeline.run_pipeline() completed")
        print(f"    ticker={metadata.get('ticker')}, fiscal_year={metadata.get('fiscal_year')}, period={metadata.get('report_period')}")
        if errors:
            print(f"    {YELLOW}Pipeline warnings/errors:{RESET} {errors}")
    except Exception as exc:
        _fail("pipeline.run_pipeline()", str(exc))
        traceback.print_exc()
        return

    # Step 2: Validate payload structure
    try:
        from pipeline.schemas import FinancialReportPayload

        validated = FinancialReportPayload(**payload)
        _pass(f"FinancialReportPayload validated: {validated.ticker} FY{validated.fiscal_year}")
    except Exception as exc:
        _fail("FinancialReportPayload schema validation", str(exc))

    # Step 3: Load to DB
    try:
        from db.loader import ensure_pipeline_runs_table, mark_processed, upsert_report

        ensure_pipeline_runs_table()
        _pass("pipeline_runs table ensured")

        if payload.get("ticker") and payload.get("fiscal_year"):
            upsert_report(payload)
            _pass(f"upsert_report: {payload['ticker']} FY{payload['fiscal_year']} written to DB")

            mark_processed(
                pdf_path,
                status="success",
                ticker=payload.get("ticker"),
                fiscal_year=payload.get("fiscal_year"),
            )
            _pass("mark_processed(success) recorded in pipeline_runs")
        else:
            _fail("upsert_report", "payload missing ticker or fiscal_year — check LLM extraction")
    except Exception as exc:
        _fail("DB load", str(exc))
        traceback.print_exc()

    # Step 4: Read back from DB and verify
    try:
        from sqlalchemy import create_engine, text

        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/finsight")
        engine = create_engine(db_url)
        ticker = payload.get("ticker", "")
        fy = payload.get("fiscal_year", 0)

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT ticker, fiscal_year FROM income_statements WHERE ticker=:t AND fiscal_year=:y"),
                {"t": ticker, "y": fy},
            ).fetchone()

        if row:
            _pass(f"DB read-back: income_statements row found for {ticker} FY{fy}")
        else:
            _fail("DB read-back", f"No income_statements row for {ticker} FY{fy}")
    except Exception as exc:
        _fail("DB read-back", str(exc))

    # Step 5: Verify pipeline_runs entry
    try:
        from sqlalchemy import create_engine, text

        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/finsight")
        engine = create_engine(db_url)

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT status FROM pipeline_runs WHERE pdf_path=:p"),
                {"p": pdf_path},
            ).fetchone()

        if row and row[0] == "success":
            _pass(f"pipeline_runs: status='success' for {os.path.basename(pdf_path)}")
        else:
            _fail("pipeline_runs status", f"Got: {row}")
    except Exception as exc:
        _fail("pipeline_runs read-back", str(exc))


# ── Watcher helper ─────────────────────────────────────────────────────────────

def watch_for_new_pdf(raw_dir: str, poll_seconds: int = 10) -> None:
    """Poll raw_dir for new PDFs and run the pipeline when one appears.

    Usage (manual trigger):
        python tests/test_pipeline.py --watch --raw-dir src/scraper/data/raw
    """
    import glob
    import time

    print(f"\n{BOLD}PDF Watcher{RESET} — polling {raw_dir!r} every {poll_seconds}s")
    print("  Drop a PDF into the directory to trigger an automatic pipeline run.")
    print("  Press Ctrl+C to stop.\n")

    seen: set = set()

    def _scan() -> set:
        return set(glob.glob(os.path.join(raw_dir, "**", "*.pdf"), recursive=True))

    seen = _scan()
    print(f"  Baseline: {len(seen)} existing PDFs")

    try:
        while True:
            time.sleep(poll_seconds)
            current = _scan()
            new_pdfs = current - seen
            if new_pdfs:
                for pdf_path in sorted(new_pdfs):
                    print(f"\n  {GREEN}New PDF detected:{RESET} {pdf_path}")
                    test_integration(pdf_path)
                seen = current
    except KeyboardInterrupt:
        print("\n  Watcher stopped.")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="FinSight ETL pipeline test suite")
    parser.add_argument("--smoke", action="store_true", help="Run only Tier 1+2 smoke tests (no DB/LLM)")
    parser.add_argument("--integration", action="store_true", help="Run Tier 3 integration test")
    parser.add_argument("--pdf", default="", help="Path to PDF for integration test")
    parser.add_argument("--watch", action="store_true", help="Watch raw PDF dir and auto-run integration test on new PDFs")
    parser.add_argument("--raw-dir", default=str(_REPO_ROOT / "src" / "scraper" / "data" / "raw"), help="Raw PDF directory for --watch mode")
    parser.add_argument("--poll", type=int, default=10, help="Polling interval in seconds for --watch mode")
    args = parser.parse_args()

    print(f"\n{BOLD}FinSight ETL Pipeline — Test Suite{RESET}")
    print(f"  Repo root : {_REPO_ROOT}")
    print(f"  Src dir   : {_SRC_DIR}")

    if args.watch:
        watch_for_new_pdf(args.raw_dir, poll_seconds=args.poll)
        return

    # Always run Tier 1 + 2
    test_imports()
    test_schemas()

    if args.integration or args.pdf:
        pdf = args.pdf
        if not pdf:
            # Try to find any existing PDF in the raw directory
            import glob
            raw = str(_REPO_ROOT / "src" / "scraper" / "data" / "raw")
            pdfs = glob.glob(os.path.join(raw, "**", "*.pdf"), recursive=True)
            if pdfs:
                pdf = pdfs[0]
                print(f"\n  {YELLOW}No --pdf specified; using first found:{RESET} {pdf}")
            else:
                print(f"\n  {YELLOW}No PDF found in {raw} — skipping Tier 3{RESET}")
                pdf = ""
        if pdf:
            test_integration(pdf)

    # Summary
    total = _PASSED + _FAILED
    colour = GREEN if _FAILED == 0 else RED
    print(f"\n{BOLD}Results:{RESET} {colour}{_PASSED}/{total} passed{RESET}", end="")
    if _FAILED:
        print(f"  {RED}({_FAILED} failed){RESET}")
    else:
        print()

    sys.exit(1 if _FAILED else 0)


if __name__ == "__main__":
    main()
