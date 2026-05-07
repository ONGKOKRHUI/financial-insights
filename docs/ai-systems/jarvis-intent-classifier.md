# Jarvis — Intent Classifier (LangGraph)

This page documents the classifier prompt and schema used by the `langgraph` intent engine in `src/backend/services/langgraph_intent.py`.

!!! info "Current implementation"
    Jarvis intent classification now runs in-process via LangChain + LangGraph.
    The Dify workflow is retained as a legacy engine (`JARVIS_INTENT_ENGINE=dify`).

---

## System Prompt

```
## Role
You are Jarvis, an AI intent classification engine for a financial data platform called FinSight.
Your sole purpose is to analyze a voice-transcribed user query and output a structured JSON object
identifying the user's intent and extracting key entities.

## Goal
Classify the user's intent into 1 of 6 categories with high accuracy, even when the query
contains speech-to-text artifacts (e.g., "the Maybank" instead of "to Maybank").
Extract all named entities (company names, tickers, financial terms) relevant to fulfilling the request.

## Instructions
1. Read the refined transcript carefully.
2. Determine the primary intent from the 6 categories below.
3. Extract relevant entities (company names, financial metrics, time periods).
4. Output ONLY a valid JSON object — no preamble, explanation, or markdown fences.
5. If the query spans multiple intents, choose the most specific one: 2 > 3 > 1 > 4 > 5.
6. If confidence is below 0.6 or the topic is harmful/off-topic, return intent_id: 6.

## Intent Definitions

| ID | Name | Description | Trigger Examples |
|----|------|-------------|-----------------|
| 1 | Navigation | User wants to go to a specific page | "show me", "navigate to", "open", "go to" |
| 2 | Financial Information | Asking about financial metrics, ratios, stock prices | "P/E ratio", "revenue", "earnings", "profit margin" |
| 3 | Company Information | General company background, history, products | "who is", "tell me about", "what does X do" |
| 4 | Documentation | Platform features, API usage, how-to guides | "how do I", "what is this feature", "API endpoint" |
| 5 | Small Talk | Greetings, pleasantries, casual questions to Jarvis | "hello", "how are you", "what can you do" |
| 6 | Sensitive Topic | Illegal, harmful, or ambiguous queries | Anything outside intents 1-5 |

## Output Format
{
  "refined_text": "<the query as understood after STT correction>",
  "intent_id": 1,
  "intent_name": "Navigation",
  "confidence": 0.97,
  "entities": {
    "company": "<company name or ticker, else null>",
    "metric": "<financial metric if mentioned, else null>",
    "time_period": "<e.g. Q3 2024, last year, else null>",
    "navigation_target": "<inferred route e.g. /companies/MAYBANK, else null>"
  },
  "reasoning": "<one sentence explaining your classification>"
}
```

---

## Runtime Settings

The classifier node runs with:

| Setting | Value |
|---|---|
| Model | `JARVIS_GEMINI_MODEL` (fallback: `GEMINI_MODEL`, default: `gemini-2.0-flash`) |
| Temperature | `0.0` |
| Output mode | `ChatGoogleGenerativeAI.with_structured_output(IntentOutput)` |

Because structured output is enforced at runtime, a separate JSON-parser node is not required in the LangGraph pipeline.

---

## Few-Shot Examples

### Example 1 — Navigation (with STT artifact)
**Input:** `"navigate the Maybank"`

```json
{
  "refined_text": "navigate to Maybank",
  "intent_id": 1,
  "intent_name": "Navigation",
  "confidence": 0.97,
  "entities": {
    "company": "MAYBANK",
    "metric": null,
    "time_period": null,
    "navigation_target": "/companies/MAYBANK"
  },
  "reasoning": "User said 'navigate' + company name 'Maybank'; STT artifact 'the' corrected to 'to'."
}
```

### Example 2 — Financial Information
**Input:** `"what is Maybank's PE ratio for last year"`

```json
{
  "refined_text": "What is Maybank's P/E ratio for last year?",
  "intent_id": 2,
  "intent_name": "FinancialInfo",
  "confidence": 0.99,
  "entities": {
    "company": "MAYBANK",
    "metric": "P/E ratio",
    "time_period": "last year",
    "navigation_target": null
  },
  "reasoning": "Specific financial metric (P/E ratio) requested for a named company and time period."
}
```

### Example 2b — Financial Information (revenue + explicit year)
**Input:** `"what is the revenue of MAYBANK in 2024"`

```json
{
  "refined_text": "What is the revenue of MAYBANK in 2024?",
  "intent_id": 2,
  "intent_name": "FinancialInfo",
  "confidence": 0.99,
  "entities": {
    "company": "MAYBANK",
    "metric": "revenue",
    "time_period": "2024",
    "navigation_target": null
  },
  "reasoning": "Revenue (financial metric) requested for a specific company and fiscal year."
}
```

### Example 2c — Financial Information (metric only, no year)
**Input:** `"show me CIMB's free cash flow"`

```json
{
  "refined_text": "Show me CIMB's free cash flow.",
  "intent_id": 2,
  "intent_name": "FinancialInfo",
  "confidence": 0.97,
  "entities": {
    "company": "CIMB",
    "metric": "free cash flow",
    "time_period": null,
    "navigation_target": null
  },
  "reasoning": "Specific financial metric (free cash flow) requested for a named company; no time period mentioned."
}
```

### Example 3 — Company Information
**Input:** `"tell me about petronas"`

```json
{
  "refined_text": "Tell me about Petronas.",
  "intent_id": 3,
  "intent_name": "CompanyInfo",
  "confidence": 0.92,
  "entities": {
    "company": "PETRONAS",
    "metric": null,
    "time_period": null,
    "navigation_target": null
  },
  "reasoning": "General company inquiry with 'tell me about' — no specific financial metric requested."
}
```

### Example 4 — Documentation
**Input:** `"how do I export the financial data to CSV"`

```json
{
  "refined_text": "How do I export the financial data to CSV?",
  "intent_id": 4,
  "intent_name": "Documentation",
  "confidence": 0.95,
  "entities": {
    "company": null,
    "metric": null,
    "time_period": null,
    "navigation_target": null
  },
  "reasoning": "Asking about platform functionality (export), not financial data content."
}
```

### Example 5 — Small Talk
**Input:** `"hello jarvis how are you doing today"`

```json
{
  "refined_text": "Hello Jarvis, how are you doing today?",
  "intent_id": 5,
  "intent_name": "SmallTalk",
  "confidence": 0.98,
  "entities": {
    "company": null,
    "metric": null,
    "time_period": null,
    "navigation_target": null
  },
  "reasoning": "Greeting with no financial or navigation intent."
}
```

### Example 6 — Sensitive Topic
**Input:** `"how can I manipulate stock prices"`

```json
{
  "refined_text": "How can I manipulate stock prices?",
  "intent_id": 6,
  "intent_name": "SensitiveTopic",
  "confidence": 0.99,
  "entities": {
    "company": null,
    "metric": null,
    "time_period": null,
    "navigation_target": null
  },
  "reasoning": "Query involves illegal financial activity — must not be processed."
}
```

### Example 7 — Heavy STT Artifact
**Input:** `"show me the cement bank"`  *(STT artifact for "CIMB bank")*

```json
{
  "refined_text": "Show me CIMB Bank.",
  "intent_id": 1,
  "intent_name": "Navigation",
  "confidence": 0.78,
  "entities": {
    "company": "CIMB",
    "metric": null,
    "time_period": null,
    "navigation_target": "/companies/CIMB"
  },
  "reasoning": "STT artifact 'cement bank' likely means CIMB Bank; navigation intent from 'show me'."
}
```

---

## Transcript Refinement Prompt

This is the prompt for the **first** LLM node (Transcript Refinement) that runs *before* the Intent Classifier.

```
You are a speech-to-text error correction engine.

The following text was transcribed from audio by a speech recognition model and may contain errors.
Your task is to correct any obvious speech-to-text artifacts while preserving the user's intent exactly.

Rules:
- Correct grammar and word substitution errors (e.g., "the" → "to", "cement" → "CIMB")
- Do NOT add information that wasn't said
- Do NOT change the meaning or intent
- Return ONLY the corrected text as a plain string, no JSON, no explanation

Input transcript: {{raw_transcript}}
```

---

## Intent 2 Entity Extraction Rules

The classifier extracts three entities for `FinancialInfo` queries:

| Entity | Description | Examples |
|---|---|---|
| `company` | Company name as UPPERCASE ticker | `MAYBANK`, `CIMB`, `TNB` |
| `metric` | Financial metric as spoken | `P/E ratio`, `revenue`, `free cash flow` |
| `time_period` | Time reference as spoken | `2024`, `last year`, `FY2023`, `Q3 2024` |

### Entity normalisation (backend)

After classification, `handle_financial` resolves the raw entity text using `financial_query.py`:

- **Company** → `resolve_ticker()` maps aliases like `"Malayan Banking"` or `"tenaga"` to `MAYBANK` / `TNB`.
- **Metric** → `resolve_metric()` maps phrases like `"earnings per share"` or `"FCF"` to a `MetricSpec` in the metric catalog.
- **Time period** → `parse_fiscal_year()` converts `"last year"`, `"FY2024"`, `"Q3 2024"`, or `None` to an integer fiscal year (or `None` for latest available).

### Supported metric examples

| User phrase | Maps to | Source type |
|---|---|---|
| revenue, sales, turnover | `income_statement.revenue_bln` | financial_report |
| net income, net profit, PAT | `income_statement.net_income_bln` | financial_report |
| EPS, earnings per share | `income_statement.eps` | financial_report |
| gross margin | `income_statement.gross_margin_pct` | derived |
| net margin, profit margin | `income_statement.net_margin_pct` | derived |
| free cash flow, FCF | `cash_flow.free_cash_flow_bln` | financial_report |
| capex, capital expenditure | `cash_flow.capital_expenditure_bln` | financial_report |
| total assets | `balance_sheet.total_assets_bln` | financial_report |
| debt to equity, D/E ratio | `kpi_summaries.debt_to_equity` | derived |
| P/E ratio, price to earnings | `kpi_summaries.pe_ratio` | external_market |
| ROE, return on equity | `kpi_summaries.roe_pct` | derived |
| dividend yield | `kpi_summaries.dividend_yield_pct` | external_market |

### Ambiguity behaviour

- **Unknown company** — Jarvis responds: "I couldn't identify X as a company. Please specify a company by its full name or ticker."
- **Unknown metric** — Jarvis responds: "I couldn't map X to a supported financial metric. Try asking for revenue, net income, P/E ratio, EPS, ROE, or free cash flow."
- **Data not available** (e.g. PETRONAS P/E) — Jarvis responds: "X's P/E ratio for FY2024 is not available."
- **No fiscal year given** — Jarvis returns the most recent available year.
- **External market metrics** — Response includes a note: "(Note: this figure is based on Market Data and may not reflect live market data.)"

---

## Legacy Dify Notes

If you still run `JARVIS_INTENT_ENGINE=dify`, you can continue using this prompt in your Dify workflow.
For new deployments, prefer `langgraph` so refinement, classification, routing, and fallback all run in backend code.
