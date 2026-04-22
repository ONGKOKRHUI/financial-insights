# PDF Parsing

!!! success "Phase 2 — Implemented"
    AI-driven PDF parsing with **LlamaParse** (primary) and **PyMuPDF** (fallback) is implemented in Phase 2.  
    Extraction uses a **two-stage architecture**: Google Gemini extracts raw strings from the full document, then Python normalises them to MYR-billion floats. All LLM calls are traced end-to-end with **Langfuse**.

---

## Overview

Malaysian public company annual/quarterly reports are complex multi-page PDFs with mixed layouts: narrative prose, multi-column financial tables, headers/footers, and embedded graphics. The FinSight parser converts these into clean structured JSON in three stages:

1. **PDF → Markdown** via LlamaParse (strict Markdown output enforced) or PyMuPDF
2. **Markdown → Raw `FinancialValue` objects** via Google Gemini with Pydantic validation
3. **`FinancialValue` → Normalised MYR-billion floats** via `normalize_financial_data()` (pure Python)

---

## Technology Stack

| Tool | Role | When Used |
|---|---|---|
| **LlamaCloud API** (`llama-cloud`) | Primary PDF → Markdown conversion (`tier=agentic`) with strict Markdown table instruction | When `LLAMA_CLOUD_API_KEY` is set |
| **PyMuPDF** (`fitz`) | Fallback plain-text extraction | When LlamaParse fails or key absent |
| **Google Gemini 2.0 Flash** (`langchain-google-genai`) | Structured LLM extraction from full Markdown; 1M-token context window | All `extract_quantitative` and `extract_qualitative` calls |
| **LangChain** (`langchain`, `langchain-core`) | Prompt templating, `with_structured_output()`, text splitter | All LLM orchestration |
| **LangGraph** (`langgraph`) | State machine routing parse → extract → validate | When `PIPELINE_ENGINE=langgraph` |
| **Pydantic v2** | Schema validation — `FinancialValue` for raw extraction, `*Schema` models for DB payload | `nodes/quantitative.py`, `src/pipeline/schemas.py`, merger node |
| **Langfuse** | LLM observability (traces, token counts, latency) | Callback on every Gemini call |

---

## Stage 1: PDF → Markdown (LlamaParse)

LlamaParse converts the PDF to Markdown using the `agentic` tier, with an explicit instruction that enforces pure Markdown table output:

```python
result = await client.parsing.parse(
    file_id=file_obj.id,
    version="latest",
    tier="agentic",
    expand=["markdown_full"],
    parsing_instruction=(
        "Strictly output all tables using standard Markdown pipe format. "
        "Do not use HTML tags like <table>, <tr>, or <td> under any circumstances."
    ),
)
markdown_text = result.markdown_full
```

The `parsing_instruction` is critical: without it LlamaParse sometimes emits complex financial tables as HTML `<table>` tags, which downstream regex or LLM prompts may fail to parse correctly.

The `agentic` tier additionally handles OCR for scanned PDFs, multi-column layouts, and header/footer separation.

If `LLAMA_CLOUD_API_KEY` is not set, the pipeline falls back to **PyMuPDF** (`fitz`) which extracts plain text (no table structure) and logs a warning.

---

## Stage 2: Markdown → Raw Strings (Gemini)

### Route Content (Pass-Through)

The `route_content` node is a simple pass-through. The full `markdown_text` is assigned to **both** `table_markdown` and `narrative_markdown`:

```python
def route_content(state):
    markdown_text = state.get("markdown_text", "")
    return {
        **state,
        "table_markdown": markdown_text,
        "narrative_markdown": markdown_text,
    }
```

No regex splitting is applied. Gemini 2.0 Flash's 1-million token context window means the full document can be sent to the LLM directly, allowing it to locate tables in any position or format.

### Quantitative Extraction (`extract_quantitative`)

The LLM receives the full document and is instructed to return values **exactly as printed** alongside the unit header from the table:

```python
class FinancialValue(BaseModel):
    raw_value: Optional[str]    # e.g. "(1,350,348)" or "12,345.00"
    unit_header: Optional[str]  # e.g. "RM 000", "MYR Millions", "sen"
```

All fields in the four extraction schemas use `Optional[FinancialValue]`:

**Income Statement (`_IncomeStatementExtraction`)**

| Field | Hint searched in document |
|---|---|
| `revenue_bln` | Revenue / Turnover / Total Income |
| `gross_profit_bln` | Gross Profit |
| `operating_income_bln` | Operating Profit / EBIT |
| `net_income_bln` | Net Profit / Profit After Tax / PAT |
| `eps` | Earnings Per Share / EPS |
| `gross_margin_pct` | Gross Margin % |
| `operating_margin_pct` | Operating Margin % |
| `net_margin_pct` | Net Margin % |

**Balance Sheet (`_BalanceSheetExtraction`)**

| Field | Hint searched in document |
|---|---|
| `total_assets_bln` | Total Assets |
| `total_liabilities_bln` | Total Liabilities |
| `total_equity_bln` | Total Equity / Shareholders' Funds |
| `cash_and_equivalents_bln` | Cash and Cash Equivalents / Bank Balances |
| `total_debt_bln` | Total Borrowings / Debt |

**Cash Flow Statement (`_CashFlowExtraction`)**

| Field | Hint searched in document |
|---|---|
| `operating_cash_flow_bln` | Net Cash from Operating Activities |
| `capital_expenditure_bln` | Capital Expenditure / Purchase of PPE / Capex |
| `free_cash_flow_bln` | Free Cash Flow (= Operating CF − Capex) |
| `dividends_paid_bln` | Dividends Paid / Dividends to Shareholders |

**KPI Summary (`_KPIExtraction`)**

| Field | Hint searched in document |
|---|---|
| `revenue_bln` | Revenue / Turnover |
| `net_income_bln` | Net Income / Profit After Tax |
| `eps` | Basic EPS / Earnings Per Share (sen or MYR) |
| `pe_ratio` | Price-to-Earnings (P/E) Ratio |
| `roe_pct` | Return on Equity (ROE) % |
| `roace_pct` | Return on Average Capital Employed (ROACE) % |
| `debt_to_equity` | Debt-to-Equity Ratio / Gearing Ratio |
| `dividend_yield_pct` | Dividend Yield % |

### Qualitative Extraction (`extract_qualitative`)

The qualitative node uses pattern-matching to locate the most relevant narrative sections (MD&A, Chairman's Statement, Outlook) before sending them to Gemini. Up to three non-overlapping section windows (~14 K chars each, capped at 20 K combined) are stitched together:

| Field | Description | DB Column |
|---|---|---|
| `future_outlook` | 2–3 sentence summary of management guidance and strategic priorities for the next 12–24 months | `future_outlook` |
| `key_strategic_events` | JSON array of significant events (acquisitions, restructurings, product launches, regulatory changes) | `key_strategic_events` |

---

## Stage 3: Raw Strings → MYR-Billion Floats (Python)

`normalize_financial_data(extracted_data: dict) -> dict` recursively walks the LLM JSON output. Whenever it finds a dict with `raw_value` and `unit_header` keys, it:

1. **Parses** the string to a float — strips commas, converts `(100)` → `-100.0`
2. **Applies a unit multiplier** to reach MYR billions:

| `unit_header` contains | Divisor | Example |
|---|---|---|
| `'000` / `thousand` / `000` | ÷ 1,000,000 | RM'000 value 12,345 → 0.012345 bln |
| `million` / `mil` | ÷ 1,000 | MYR Millions value 1,234.5 → 1.2345 bln |
| `billion` / `bil` | ÷ 1 (no-op) | RM billion value 1.23 → 1.23 bln |
| unrecognised | ÷ 1 + warning log | kept as-is |

3. **Replaces** the nested `FinancialValue` dict with the final `float` in-place

This keeps all arithmetic deterministic and auditable in Python, removing the risk of LLM unit-conversion errors.

---

## Output JSON Schema

After normalisation the pipeline produces a `FinancialReportPayload` dict:

```json
{
  "ticker": "MAYBANK",
  "fiscal_year": 2024,
  "report_period": "Q3",
  "source_pdf": "/app/src/scraper/data/raw/MAYBANK/MAYBANK_2024_Q3.pdf",
  "income_statement": {
    "ticker": "MAYBANK",
    "fiscal_year": 2024,
    "revenue_bln": 12.345,
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

All monetary `_bln` fields are normalised MYR-billion floats. Percentages are 0–100. `key_strategic_events` is a JSON-serialised string.

---

## Metadata Extraction (from Filename)

The scraper saves files as `{TICKER}_{YEAR}_{QUARTER}.pdf`. The parser derives:

```python
# MAYBANK_2024_Q3.pdf →
ticker        = "MAYBANK"
fiscal_year   = 2024
report_period = "Q3"
```

---

## Gemini Structured Extraction — Code Pattern

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
structured_llm = llm.with_structured_output(_IncomeStatementExtraction)
chain = _EXTRACTION_PROMPT | structured_llm

# Full document passed — no chunking or windowing
result = chain.invoke({
    "ticker": "MAYBANK",
    "fiscal_year": 2024,
    "content": full_markdown_text,   # entire document
    ...
})

# result fields are FinancialValue objects, e.g.:
# result.revenue_bln = FinancialValue(raw_value="12,345,678", unit_header="RM '000")
```

---

## Quality Checks

| Check | Where |
|---|---|
| Raw values must be strings or `null` | Pydantic `FinancialValue.raw_value: Optional[str]` |
| Normalised values are Python floats — no LLM arithmetic | `normalize_financial_data()` |
| Unrecognised unit headers logged as warnings | `_unit_multiplier()` in `quantitative.py` |
| Ticker and fiscal_year required in final payload | `merge_and_validate` node |
| Validation errors append to `state.errors` — partial payload still loaded | merger node |
| DB UPSERT rejects payloads with empty ticker/year | `db.loader.upsert_report()` |
| Each run recorded in `pipeline_runs` with status + error_msg | `db.loader.mark_processed()` |

---

## Known Limitations

| Limitation | Status |
|---|---|
| Scanned PDFs with no text layer | LlamaParse handles with OCR at `agentic` tier; PyMuPDF fallback will produce empty output — logs a warning |
| Non-standard table formats (merged cells, rotated headers) | LlamaParse mitigates; some values may be `null`; `parsing_instruction` enforces Markdown output |
| Multi-language content (Bahasa Malaysia sections) | Gemini handles BM but may miss technical terms — affected field returns `null` |
| HTML table output from LlamaParse | Mitigated by `parsing_instruction`; PyMuPDF fallback strips all formatting |
| PDFs requiring authenticated access | Scraper handles download; parser assumes local file |
