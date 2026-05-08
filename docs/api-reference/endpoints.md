# Endpoints

!!! success "Phase 3 — Live"
    All endpoints below are live at `https://finsight-api.onrender.com`.
    No authentication is required.

---

## Health

### `GET /health`

Liveness probe. Returns HTTP 200 when the server is running.

**Response**

```json
{ "status": "ok" }
```

---

## Companies

### `GET /companies`

Returns a summary list of all 8 covered companies.

**Response** — array of `CompanySummary`

```json
[
  {
    "ticker": "MAYBANK",
    "name": "Malayan Banking Berhad",
    "sector": "Financials",
    "market_cap_bln": 102.4,
    "currency": "MYR"
  },
  ...
]
```

---

### `GET /companies/{ticker}`

Returns the full company profile for a single company.

**Path Parameters**

| Parameter | Type   | Description                          |
|-----------|--------|--------------------------------------|
| `ticker`  | string | KLSE ticker symbol, e.g. `MAYBANK`   |

**Response** — `CompanyDetail`

```json
{
  "ticker": "MAYBANK",
  "name": "Malayan Banking Berhad",
  "sector": "Financials",
  "industry": "Banking",
  "description": "Maybank is Malaysia's largest bank...",
  "market_cap_bln": 102.4,
  "employees": 43000,
  "founded": 1960,
  "headquarters": "Kuala Lumpur, Malaysia",
  "website": "https://www.maybank.com",
  "currency": "MYR",
  "exchange": "KLSE"
}
```

**Errors**

| Status | Condition                    |
|--------|------------------------------|
| 404    | Ticker not found in database |

---

### `GET /companies/{ticker}/summary`

Returns the latest-year KPI snapshot for a company.

**Path Parameters**

| Parameter | Type   | Description             |
|-----------|--------|-------------------------|
| `ticker`  | string | KLSE ticker symbol      |

**Response** — `KPISummary`

```json
{
  "ticker": "MAYBANK",
  "revenue_bln": 30.2,
  "net_income_bln": 9.1,
  "eps": 0.86,
  "pe_ratio": 12.4,
  "roe_pct": 10.8,
  "roace_pct": 8.2,
  "debt_to_equity": 0.92,
  "dividend_yield_pct": 5.8,
  "fiscal_year": 2024
}
```

**Errors**

| Status | Condition               |
|--------|-------------------------|
| 404    | Ticker not found        |

---

### `GET /companies/{ticker}/qualitative`

Returns the latest qualitative insight: a future outlook paragraph and a list
of key strategic events.

**Path Parameters**

| Parameter | Type   | Description         |
|-----------|--------|---------------------|
| `ticker`  | string | KLSE ticker symbol  |

**Response** — `QualitativeInsight`

```json
{
  "ticker": "MAYBANK",
  "fiscal_year": 2024,
  "future_outlook": "Maybank remains well-positioned to leverage ASEAN growth...",
  "key_strategic_events": [
    "Expanded ASEAN digital banking operations",
    "Launched M25+ strategic plan targeting RM100bn market cap"
  ]
}
```

---

## Financial Statements

### `GET /financials/{ticker}/income-statement`

Returns 5 years of annual income statement data for a company.

**Path Parameters**

| Parameter | Type   | Description         |
|-----------|--------|---------------------|
| `ticker`  | string | KLSE ticker symbol  |

**Response** — `IncomeStatementResponse`

```json
{
  "ticker": "MAYBANK",
  "name": "Malayan Banking Berhad",
  "currency": "MYR",
  "data": [
    {
      "fiscal_year": 2020,
      "revenue_bln": 24.1,
      "gross_profit_bln": 18.3,
      "operating_income_bln": 10.2,
      "net_income_bln": 6.5,
      "eps": 0.61,
      "gross_margin_pct": 75.9,
      "operating_margin_pct": 42.3,
      "net_margin_pct": 27.0
    },
    ...
  ]
}
```

Data entries are ordered by `fiscal_year` ascending (oldest first).

---

### `GET /financials/{ticker}/balance-sheet`

Returns 5 years of annual balance sheet data.

**Path Parameters**

| Parameter | Type   | Description         |
|-----------|--------|---------------------|
| `ticker`  | string | KLSE ticker symbol  |

**Response** — `BalanceSheetResponse`

```json
{
  "ticker": "CIMB",
  "name": "CIMB Group Holdings Berhad",
  "currency": "MYR",
  "data": [
    {
      "fiscal_year": 2024,
      "total_assets_bln": 652.3,
      "total_liabilities_bln": 596.1,
      "total_equity_bln": 56.2,
      "cash_and_equivalents_bln": 38.4,
      "total_debt_bln": 18.7
    }
  ]
}
```

---

### `GET /financials/{ticker}/cash-flow`

Returns 5 years of annual cash flow data.

**Path Parameters**

| Parameter | Type   | Description         |
|-----------|--------|---------------------|
| `ticker`  | string | KLSE ticker symbol  |

**Response** — `CashFlowResponse`

```json
{
  "ticker": "TNB",
  "name": "Tenaga Nasional Berhad",
  "currency": "MYR",
  "data": [
    {
      "fiscal_year": 2024,
      "operating_cash_flow_bln": 12.4,
      "capital_expenditure_bln": -6.8,
      "free_cash_flow_bln": 5.6,
      "dividends_paid_bln": -2.1
    }
  ]
}
```

---

## Search

### `GET /search/live`

Search-as-you-type endpoint that returns the top 5 most relevant docs/page
suggestions for a partial query string using edge n-gram BM25 over the indexed
webpage content.  Designed for per-keystroke calls from the frontend.

**Authentication** — requires a valid session cookie or `X-API-Key` header.

**Query Parameters**

| Parameter | Type   | Required | Description                             |
|-----------|--------|----------|-----------------------------------------|
| `q`       | string | yes      | Partial search query (2–200 characters) |

**Example Request**

```bash
curl -H "X-API-Key: your_api_key" \
  "https://finsight-api.onrender.com/search/live?q=jarvis"
```

**Response** — `LiveSearchResponse`

```json
{
  "query": "jarvis",
  "total": 3,
  "hits": [
    {
      "rank": 1,
      "title": "Jarvis Voice Assistant Overview",
      "snippet": "Hands-free navigation by voice using Gemini ASR and the browser Web Speech API.",
      "source_path": "docs/ai-systems/jarvis-overview.md",
      "source_uri": "https://finsight.dev/ai-systems/jarvis-overview/",
      "score": 1.403281,
      "doc_type": "project_doc",
      "domain": "platform",
      "ticker": null
    }
  ]
}
```

**Errors**

| Status | Condition                                              |
|--------|--------------------------------------------------------|
| 401    | Missing or expired session cookie / API key            |
| 422    | `q` missing or shorter than 2 characters               |
| 503    | Elasticsearch unavailable                              |

---

### `POST /search`

Unified payload-based query endpoint. Send `ticker`, `statement_type`, and
an optional `fiscal_year` to retrieve any financial record from a single
endpoint. Omit `fiscal_year` to receive the most recent available year.

**Request Body**

| Field            | Type    | Required | Description                                                       |
|------------------|---------|----------|-------------------------------------------------------------------|
| `ticker`         | string  | yes      | KLSE ticker symbol                                               |
| `statement_type` | enum    | yes      | `income_statement` \| `balance_sheet` \| `cash_flow` \| `kpi` \| `qualitative` |
| `fiscal_year`    | integer | no       | Specific year; omit for latest                                   |

**Example Request**

```bash
curl -X POST "https://finsight-api.onrender.com/search" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "MAYBANK", "statement_type": "income_statement"}'
```

**Response** — `SearchResponse`

```json
{
  "ticker": "MAYBANK",
  "statement_type": "income_statement",
  "fiscal_year": 2024,
  "data": {
    "fiscal_year": 2024,
    "revenue_bln": 30.2,
    "gross_profit_bln": 22.8,
    "operating_income_bln": 12.4,
    "net_income_bln": 9.1,
    "eps": 0.86,
    "gross_margin_pct": 75.5,
    "operating_margin_pct": 41.1,
    "net_margin_pct": 30.1
  }
}
```

**Errors**

| Status | Condition                              |
|--------|----------------------------------------|
| 404    | Ticker not found                       |
| 422    | Invalid `statement_type` value         |

---

## Covered Tickers

The following ticker symbols are valid for all financial endpoints:

| Ticker    | Company                    | Sector                     |
|-----------|----------------------------|----------------------------|
| MAYBANK   | Malayan Banking Berhad     | Financials                 |
| CIMB      | CIMB Group Holdings Berhad | Financials                 |
| TNB       | Tenaga Nasional Berhad     | Utilities                  |
| PETRONAS  | Petroliam Nasional Berhad  | Energy                     |
| MAXIS     | Maxis Berhad               | Communication Services     |
| TM        | Telekom Malaysia Berhad    | Communication Services     |
| GENTING   | Genting Berhad             | Consumer Discretionary     |
| SUNWAY    | Sunway Berhad              | Real Estate                |

New tickers can be added by inserting company + financial rows into the database and updating `COMPANY_ALIASES` in `services/financial_query.py`. No endpoint or handler code needs to change.

---

## Jarvis Voice API

### `POST /api/jarvis/intent/stream`

Natural-language voice intent endpoint (primary path — text input).

**Request Body (FormData)**

| Field | Type | Description |
|---|---|---|
| `text` | string | Refined transcript text from the browser Web Speech API |
| `session_id` | string (optional) | Client session identifier |

**Response** — Server-Sent Events (SSE) stream

```json
{ "event": "response", "data": { "action": "respond", "message": "MAYBANK's revenue for FY2024 was MYR 30.20 billion.", "voice": "...", "intent_id": 2, "sources": [...], "confidence": 0.99, "engine": "langgraph" } }
```

**Intent 2 (FinancialInfo) example**

```bash
curl -X POST "https://finsight-api.onrender.com/api/jarvis/intent/stream" \
  -H "X-API-Key: your_api_key" \
  -F "text=what is the revenue of MAYBANK in 2024"
```

The backend resolves `MAYBANK` → ticker, `revenue` → `income_statement.revenue_bln`, `2024` → FY2024, then queries PostgreSQL and returns a grounded answer.

---

## RAG

### `POST /rag/ask`

Natural-language documentation and company question answering using Elasticsearch hybrid retrieval.

**Request Body**

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | string | yes | Natural-language question |
| `scope` | string | no | `documentation`, `company`, or `all` (default: `all`) |
| `ticker` | string | no | Restrict to a specific company |
| `top_k` | integer | no | Number of source chunks (1–12, default: 6) |
| `include_sources` | boolean | no | Include source citations (default: true) |

**Example**

```bash
curl -X POST "https://finsight-api.onrender.com/rag/ask" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"question": "How does Jarvis voice navigation work?", "scope": "documentation"}'
```

**Response** — `RagAskResponse`

```json
{
  "answer": "Jarvis uses the browser Web Speech API for live transcription...",
  "question": "How does Jarvis voice navigation work?",
  "scope": "documentation",
  "sources": [
    { "chunk_id": "...", "title": "Jarvis Architecture", "source_path": "docs/ai-systems/jarvis-architecture.md", "snippet": "...", "rank": 1 }
  ],
  "retrieval": { "strategy": "hybrid_rrf", "lexical_hits": 12, "vector_hits": 10, "fused_hits": 6 },
  "confidence": "high",
  "abstained": false
}
```
