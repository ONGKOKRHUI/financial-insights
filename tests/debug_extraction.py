"""Diagnostic script: test quantitative + qualitative LLM extraction directly.

Usage:
    # Test on a real PDF (uses LlamaParse, same as the full pipeline)
    python tests/debug_extraction.py --pdf src/scraper/data/raw/SUNWAY/SUNWAY_2021_Q1.pdf

    # Force PyMuPDF fallback (without LlamaParse)
    python tests/debug_extraction.py --pdf <path> --no-llama

    # Test on a small inline text snippet (no PDF needed)
    python tests/debug_extraction.py --snippet

    # Enable verbose DEBUG logging to see which section window was chosen
    python tests/debug_extraction.py --pdf <path> --debug
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# PYTHONPATH bootstrap
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

try:
    from dotenv import load_dotenv
    #load_dotenv(_REPO_ROOT / ".env")
    load_dotenv(_REPO_ROOT / ".env", override=True)

except ImportError:
    pass

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

_MINI_SNIPPET = """\
## Condensed Income Statement (RM million)

| Item                         | Q1 FY2021 | Q1 FY2020 |
|------------------------------|----------:|----------:|
| Revenue                      |   1,234.5 |   1,100.2 |
| Gross Profit                 |     345.6 |     310.0 |
| Operating Profit (EBIT)      |     210.3 |     195.7 |
| Net Profit After Tax         |     150.8 |     140.2 |
| Earnings Per Share (sen)     |      7.80 |      7.25 |
| Gross Margin (%)             |      28.0 |      28.2 |
| Operating Margin (%)         |      17.0 |      17.8 |
| Net Margin (%)               |      12.2 |      12.7 |

## Condensed Balance Sheet (RM million)

| Item                         | 31 Mar 2021 | 31 Dec 2020 |
|------------------------------|------------:|------------:|
| Total Assets                 |    15,678.9 |    14,900.3 |
| Total Liabilities            |     9,234.5 |     8,800.1 |
| Total Equity                 |     6,444.4 |     6,100.2 |
| Cash and Cash Equivalents    |     1,200.0 |     1,050.5 |
| Total Borrowings             |     4,500.0 |     4,200.0 |

## Condensed Cash Flow Statement (RM million)

| Item                                     | Q1 FY2021 |
|------------------------------------------|----------:|
| Net Cash from Operating Activities       |     380.5 |
| Capital Expenditure (Capex)              |    (120.3)|
| Dividends Paid                           |     (75.0)|

## Outlook
The Group remains cautiously optimistic for the remainder of FY2021, underpinned by a robust
order book of RM 8.5 billion and continued recovery in the property segment.
Management targets double-digit revenue growth for the full year, supported by the newly
acquired Sunway Medical Centre Towers project and expansion into Vietnam.
"""


def _get_text_from_pdf(pdf_path: str, use_llama: bool = True) -> str:
    """Parse PDF using LlamaParse (pipeline path) or PyMuPDF fallback."""
    if use_llama and os.getenv("LLAMA_CLOUD_API_KEY"):
        print(f"  [LlamaParse] Uploading PDF to LlamaCloud …")
        try:
            from pipeline.nodes.parser import _llamaparse
            import asyncio
            text = asyncio.run(_llamaparse(pdf_path))
            if text:
                print(f"  [OK] LlamaParse returned {len(text):,} chars (Markdown)")
                return text
            else:
                print(f"  [WARN] LlamaParse returned empty string — falling back to PyMuPDF")
        except Exception as exc:
            print(f"  [WARN] LlamaParse failed ({exc}) — falling back to PyMuPDF")
    elif use_llama:
        print(f"  [WARN] LLAMA_CLOUD_API_KEY not set — falling back to PyMuPDF")

    # PyMuPDF fallback
    try:
        import fitz  # pymupdf
        doc = fitz.open(pdf_path)
        pages = [page.get_text("text") for page in doc]
        doc.close()
        text = "\n\n".join(pages)
        print(f"  [OK] PyMuPDF extracted {len(text):,} chars from PDF")
        return text
    except Exception as exc:
        print(f"  [FAIL] PyMuPDF also failed: {exc}")
        return ""


def _route(markdown_text: str) -> tuple[str, str]:
    """Run the real router so we split the same way the pipeline does."""
    from pipeline.nodes.router import route_content
    result = route_content({"markdown_text": markdown_text, "errors": []})
    table_md = result["table_markdown"]
    narrative_md = result["narrative_markdown"]
    print(
        f"  [Router] table_markdown={len(table_md):,} chars | "
        f"narrative_markdown={len(narrative_md):,} chars"
    )
    return table_md, narrative_md


def _run_quantitative(table_markdown: str, metadata: dict) -> None:
    from pipeline.nodes.quantitative import (
        _build_llm,
        _build_langfuse_callback,
        _extract_statement,
        _IncomeStatementExtraction,
        _BalanceSheetExtraction,
        _CashFlowExtraction,
        _KPIExtraction,
        normalize_financial_data,
    )

    llm = _build_llm()
    cb = _build_langfuse_callback()
    callbacks = [cb] if cb else []

    statements = [
        ("Income Statement",    _IncomeStatementExtraction),
        ("Balance Sheet",       _BalanceSheetExtraction),
        ("Cash Flow Statement", _CashFlowExtraction),
        ("KPI Summary",         _KPIExtraction),
    ]

    print(f"\n{BOLD}[Quantitative Extraction]{RESET}")
    for statement_type, schema in statements:
        print(f"\n  {YELLOW}>> {statement_type}{RESET}  (Full Document: {len(table_markdown):,} chars)")

        raw_result = _extract_statement(llm, schema, statement_type, table_markdown, metadata, callbacks)
        result = normalize_financial_data(raw_result)
        
        populated = {k: v for k, v in result.items() if v is not None}
        null_keys = [k for k, v in result.items() if v is None]
        
        if populated:
            for k, v in populated.items():
                print(f"    {GREEN}[OK]{RESET}   {k}: {v}")
        else:
            print(f"    {RED}[FAIL]{RESET} ALL fields returned None")
        if null_keys:
            print(f"    {YELLOW}[NULL]{RESET} {null_keys}")


def _run_qualitative(narrative_markdown: str, metadata: dict) -> None:
    from pipeline.nodes.qualitative import (
        _build_llm,
        _build_langfuse_callback,
        _QUALITATIVE_PROMPT,
        _QualitativeExtraction,
        _find_narrative_window,
    )

    llm = _build_llm()
    cb = _build_langfuse_callback()
    callbacks = [cb] if cb else []

    structured_llm = llm.with_structured_output(_QualitativeExtraction)
    chain = _QUALITATIVE_PROMPT | structured_llm

    primary_chunk = _find_narrative_window(narrative_markdown)
    print(f"\n{BOLD}[Qualitative Extraction]{RESET}  (window: {len(primary_chunk):,} chars)")

    try:
        result = chain.invoke(
            {
                "ticker": metadata.get("ticker", "UNKNOWN"),
                "fiscal_year": metadata.get("fiscal_year", "UNKNOWN"),
                "report_period": metadata.get("report_period", "UNKNOWN"),
                "content": primary_chunk,
            },
            config={"callbacks": callbacks},
        )
        data = result.model_dump() if result else {}
        for k, v in data.items():
            if v is not None:
                print(f"  {GREEN}[OK]{RESET}   {k}: {str(v)[:200]}")
            else:
                print(f"  {RED}[NULL]{RESET} {k}: None")
    except Exception as exc:
        print(f"  {RED}[FAIL]{RESET} Qualitative extraction error: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Debug LLM extraction directly")
    parser.add_argument("--pdf", default="", help="Path to PDF to test against")
    parser.add_argument("--snippet", action="store_true", help="Use built-in mini snippet instead")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG log level")
    parser.add_argument("--no-llama", action="store_true", help="Skip LlamaParse and use PyMuPDF directly")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")

    if not os.getenv("GOOGLE_API_KEY"):
        print(f"{RED}ERROR: GOOGLE_API_KEY not set in environment / .env{RESET}")
        sys.exit(1)
    else:
        print(f"{GREEN}GOOGLE_API_KEY is set in environment which is {os.getenv('GOOGLE_API_KEY')}{RESET}")

    metadata = {"ticker": "SUNWAY", "fiscal_year": 2021, "report_period": "Q1"}

    if args.snippet:
        raw_text = _MINI_SNIPPET
        print(f"{BOLD}Using built-in mini snippet ({len(raw_text)} chars){RESET}")
    elif args.pdf:
        use_llama = not args.no_llama
        parse_method = "LlamaParse" if (use_llama and os.getenv("LLAMA_CLOUD_API_KEY")) else "PyMuPDF"
        print(f"{BOLD}Extracting text from PDF:{RESET} {args.pdf}")
        print(f"  Parse method: {parse_method}")
        raw_text = _get_text_from_pdf(args.pdf, use_llama=use_llama)
        if not raw_text:
            print(f"{RED}No text extracted -- aborting{RESET}")
            sys.exit(1)
        stem = Path(args.pdf).stem.split("_")
        if len(stem) >= 3:
            metadata["ticker"] = stem[0]
            try:
                metadata["fiscal_year"] = int(stem[1])
            except ValueError:
                pass
            metadata["report_period"] = "_".join(stem[2:])
    else:
        print(f"{YELLOW}No --pdf or --snippet specified. Using built-in snippet.{RESET}")
        raw_text = _MINI_SNIPPET

    print(f"\n  Metadata : {metadata}")
    print(f"  Raw text : {len(raw_text):,} chars\n")

    # Route the content the same way the pipeline does
    table_md, narrative_md = _route(raw_text)

    _run_quantitative(table_md, metadata)
    _run_qualitative(narrative_md, metadata)


if __name__ == "__main__":
    main()