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
    load_dotenv(_REPO_ROOT / ".env", override=True)
except ImportError:
    pass

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


# ---------------- PDF PARSING ----------------

def _get_text_from_pdf(pdf_path: str, use_llama: bool = True) -> str:
    if use_llama and os.getenv("LLAMA_CLOUD_API_KEY"):
        print(f"  [LlamaParse] Uploading PDF...")
        try:
            from pipeline.nodes.parser import _llamaparse
            import asyncio
            text = asyncio.run(_llamaparse(pdf_path))
            if text:
                print(f"  [OK] Parsed {len(text):,} chars")
                return text
        except Exception as exc:
            print(f"  [WARN] LlamaParse failed: {exc}")

    # fallback
    try:
        import fitz
        doc = fitz.open(pdf_path)
        text = "\n\n".join(page.get_text("text") for page in doc)
        doc.close()
        print(f"  [OK] PyMuPDF extracted {len(text):,} chars")
        return text
    except Exception as exc:
        print(f"  [FAIL] PDF parsing failed: {exc}")
        return ""


# ---------------- ROUTER ----------------

def _route(markdown_text: str):
    from pipeline.nodes.router import route_content
    result = route_content({"markdown_text": markdown_text, "errors": []})
    print(f"  [Router] table={len(result['table_markdown']):,} | narrative={len(result['narrative_markdown']):,}")
    return result["table_markdown"], result["narrative_markdown"]


# ---------------- LLM ----------------

def _run_quantitative(table_markdown: str, metadata: dict):
    from pipeline.nodes.quantitative import (
        _build_llm, _extract_statement,
        _IncomeStatementExtraction, _BalanceSheetExtraction,
        _CashFlowExtraction, _KPIExtraction,
        normalize_financial_data,
    )

    llm = _build_llm()

    print(f"\n{BOLD}[Quantitative]{RESET}")
    for name, schema in [
        ("Income", _IncomeStatementExtraction),
        ("Balance", _BalanceSheetExtraction),
        ("CashFlow", _CashFlowExtraction),
        ("KPI", _KPIExtraction),
    ]:
        print(f"  >> {name}")
        result = normalize_financial_data(
            _extract_statement(llm, schema, name, table_markdown, metadata, [])
        )
        print(f"    {GREEN}Extracted fields:{RESET} {list(result.keys())}")


def _run_qualitative(narrative_markdown: str, metadata: dict):
    from pipeline.nodes.qualitative import (
        _build_llm, _QUALITATIVE_PROMPT,
        _QualitativeExtraction, _find_narrative_window
    )

    llm = _build_llm()
    chunk = _find_narrative_window(narrative_markdown)

    chain = _QUALITATIVE_PROMPT | llm.with_structured_output(_QualitativeExtraction)

    print(f"\n{BOLD}[Qualitative]{RESET}")

    try:
        result = chain.invoke({
            "ticker": metadata["ticker"],
            "fiscal_year": metadata["fiscal_year"],
            "report_period": metadata["report_period"],
            "content": chunk,
        })
        print(f"  {GREEN}Qualitative extracted{RESET}")
        return result.model_dump()
    except Exception as e:
        print(f"  {RED}Qualitative failed: {e}{RESET}")
        return {}


# ---------------- CORE PIPELINE ----------------

def process_single_pdf(pdf_path: Path, args):
    print(f"\n{BOLD}=============================={RESET}")
    print(f"{BOLD}Processing:{RESET} {pdf_path}")

    metadata = {"ticker": "UNKNOWN", "fiscal_year": "UNKNOWN", "report_period": "UNKNOWN"}

    # Extract metadata
    parts = pdf_path.stem.split("_")
    if len(parts) >= 3:
        metadata["ticker"] = parts[0]
        try:
            metadata["fiscal_year"] = int(parts[1])
        except:
            pass
        metadata["report_period"] = "_".join(parts[2:])

    raw_text = _get_text_from_pdf(str(pdf_path), not args.no_llama)

    if not raw_text:
        print(f"{RED}Skipping (no text){RESET}")
        return

    table_md, narrative_md = _route(raw_text)

    _run_quantitative(table_md, metadata)
    _run_qualitative(narrative_md, metadata)

    print(f"\n{GREEN}{BOLD}DONE processing {pdf_path.name}{RESET}")
    
    import time
    time.sleep(2)


# ---------------- UTILS ----------------

def _get_all_pdfs(folder):
    return list(Path(folder).rglob("*.pdf"))


# ---------------- MAIN ----------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default="")
    parser.add_argument("--data-dir", default="src/scraper/data/raw")
    parser.add_argument("--no-llama", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if not os.getenv("GOOGLE_API_KEY"):
        print(f"{RED}Missing GOOGLE_API_KEY{RESET}")
        sys.exit(1)

    # SINGLE FILE
    if args.pdf:
        process_single_pdf(Path(args.pdf), args)
        return

    # MULTIPLE FILES
    pdfs = _get_all_pdfs(args.data_dir)

    if not pdfs:
        print(f"{RED}No PDFs found{RESET}")
        return

    print(f"{BOLD}Found {len(pdfs)} PDFs{RESET}")

    for pdf in pdfs:
        try:
            process_single_pdf(pdf, args)
        except Exception as e:
            print(f"{RED}Error with {pdf}: {e}{RESET}")


if __name__ == "__main__":
    main()