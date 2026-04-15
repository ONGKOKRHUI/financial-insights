# PDF Parsing

!!! success "Phase 2 — Implemented"
    AI-driven PDF parsing with **LlamaParse** (primary) and **PyMuPDF** (fallback) is implemented in Phase 2.  
    Extraction is handled by **Google Gemini** via LangChain structured output, traced end-to-end with **Langfuse**.

---

## Overview

Malaysian public company annual/quarterly reports are complex multi-page PDFs with mixed layouts: narrative prose, multi-column financial tables, headers/footers, and embedded graphics. The FinSight parser converts these into clean structured JSON in two stages:

1. **PDF → Markdown** via LlamaParse or PyMuPDF  
2. **Markdown → Structured JSON** via Google Gemini with Pydantic validation

---

## Technology Stack

| Tool | Role | When Used |
|---|---|---|
| **LlamaCloud API** (`llama-cloud`) | Primary PDF → Markdown conversion (`tier=agentic`) | When `LLAMA_CLOUD_API_KEY` is set |
| **PyMuPDF** (`fitz`) | Fallback plain-text extraction | When LlamaParse fails or key absent |
| **Google Gemini** (`langchain-google-genai`) | Structured LLM extraction from Markdown | All `extract_quantitative` and `extract_qualitative` calls |
| **LangChain** (`langchain`, `langchain-core`) | Prompt templating, `with_structured_output()`, text splitter | All LLM orchestration |
| **LangGraph** (`langgraph`) | State machine routing parse → extract → validate | When `PIPELINE_ENGINE=langgraph` |
| **Pydantic v2** | Schema validation of extracted values | `src/pipeline/schemas.py`, merger node |
| **Langfuse** | LLM observability (traces, token counts, latency) | Callback on every Gemini call |

---

## Extraction Targets

### Financial Tables (`extract_quantitative`)

Extracted from the `table_markdown` sub-string (Markdown rows with `|` delimiters).

**Income Statement**

| Field | Unit | DB Column |
|---|---|---|
| Revenue | MYR bln | `revenue_bln` |
| Gross Profit | MYR bln | `gross_profit_bln` |
| Operating Income | MYR bln | `operating_income_bln` |
| Net Income | MYR bln | `net_income_bln` |
| EPS | MYR | `eps` |
| Gross Margin | % | `gross_margin_pct` |
| Operating Margin | % | `operating_margin_pct` |
| Net Margin | % | `net_margin_pct` |

**Balance Sheet**

| Field | Unit | DB Column |
|---|---|---|
| Total Assets | MYR bln | `total_assets_bln` |
| Total Liabilities | MYR bln | `total_liabilities_bln` |
| Total Equity | MYR bln | `total_equity_bln` |
| Cash & Equivalents | MYR bln | `cash_and_equivalents_bln` |
| Total Debt | MYR bln | `total_debt_bln` |

**Cash Flow Statement**

| Field | Unit | DB Column |
|---|---|---|
| Operating Cash Flow | MYR bln | `operating_cash_flow_bln` |
| Capital Expenditure | MYR bln | `capital_expenditure_bln` |
| Free Cash Flow | MYR bln | `free_cash_flow_bln` |
| Dividends Paid | MYR bln | `dividends_paid_bln` |

**KPI Summary**

| Field | Unit | DB Column |
|---|---|---|
| Revenue | MYR bln | `revenue_bln` |
| Net Income | MYR bln | `net_income_bln` |
| EPS | MYR | `eps` |
| P/E Ratio | × | `pe_ratio` |
| ROE | % | `roe_pct` |
| ROACE | % | `roace_pct` |
| Debt-to-Equity | × | `debt_to_equity` |
| Dividend Yield | % | `dividend_yield_pct` |

### Narrative Text (`extract_qualitative`)

Extracted from the `narrative_markdown` sub-string (prose sections).

| Field | Description | DB Column |
|---|---|---|
| Future Outlook | 2–3 sentence summary of management guidance and strategic priorities | `future_outlook` |
| Key Strategic Events | JSON array of significant events (acquisitions, restructurings, product launches) | `key_strategic_events` |

### Metadata (from filename)

The scraper saves files as `{TICKER}_{YEAR}_{QUARTER}.pdf`. The parser derives:

```python
# MAYBANK_2024_Q3.pdf →
ticker       = "MAYBANK"
fiscal_year  = 2024
report_period = "Q3"
```

---

## Output JSON Schema

```json
{
  "ticker": "MAYBANK",
  "fiscal_year": 2024,
  "report_period": "Q3",
  "source_pdf": "/app/src/scraper/data/raw/MAYBANK/MAYBANK_2024_Q3.pdf",
  "income_statement": {
    "ticker": "MAYBANK",
    "fiscal_year": 2024,
    "revenue_bln": 12.5,
    "gross_profit_bln": 8.1,
    "net_income_bln": 2.3,
    "eps": 0.22,
    "net_margin_pct": 18.4
  },
  "balance_sheet": {
    "total_assets_bln": 100.0,
    "total_equity_bln": 20.0,
    "total_debt_bln": 15.3
  },
  "cash_flow": {
    "operating_cash_flow_bln": 3.1,
    "capital_expenditure_bln": 0.9,
    "free_cash_flow_bln": 2.2
  },
  "qualitative_insight": {
    "future_outlook": "Management remains cautiously optimistic for FY2025, targeting double-digit loan growth.",
    "key_strategic_events": "[\"Digital banking licence granted\", \"Acquired 20% stake in regional fintech\"]"
  },
  "kpi_summary": {
    "roe_pct": 11.5,
    "debt_to_equity": 0.8,
    "dividend_yield_pct": 5.2
  }
}
```

---

## LlamaParse Integration

```python
from llama_cloud import AsyncLlamaCloud

client = AsyncLlamaCloud(api_key=os.getenv("LLAMA_CLOUD_API_KEY"))

file_obj = await client.files.create(
    file=(filename, pdf_bytes, "application/pdf"),
    purpose="parse",
)
result = await client.parsing.parse(
    file_id=file_obj.id,
    tier="agentic",          # highest-quality parsing tier
    expand=["markdown_full"],
)
markdown_text = result.markdown_full
```

The `agentic` tier preserves table structure, handles multi-column layouts, and correctly handles headers/footers in Malaysian financial reports.

---

## Gemini Structured Extraction

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
structured_llm = llm.with_structured_output(IncomeStatementSchema)
chain = prompt | structured_llm
result = chain.invoke({"content": table_markdown, ...})
```

Gemini is instructed to return `null` for any field it cannot find with confidence, preventing hallucinated numbers.

---

## Quality Checks

| Check | Where |
|---|---|
| All monetary values must be `float` or `null` | Pydantic schema `Optional[float]` |
| Ticker and fiscal_year required in final payload | `merge_and_validate` node |
| Validation errors append to `state.errors` — partial payload still loaded | merger node |
| DB UPSERT rejects payloads with empty ticker/year | `db.loader.upsert_report()` |
| Each run recorded in `pipeline_runs` with status + error_msg | `db.loader.mark_processed()` |

---

## Known Limitations

| Limitation | Status |
|---|---|
| Scanned PDFs with no text layer | LlamaParse handles with OCR at `agentic` tier; PyMuPDF fallback will fail — logs a warning |
| Non-standard table formats (merged cells, rotated headers) | LlamaParse mitigates; some values may be `null` |
| Multi-language content (Bahasa Malaysia sections) | Gemini handles BM but may miss technical terms — field returns `null` |
| Very large PDFs (>200 pages) | Table markdown is trimmed to 8,000 chars; narrative to 10,000 chars for Gemini context |
| PDFs requiring authenticated access | Scraper handles download; parser assumes local file |
