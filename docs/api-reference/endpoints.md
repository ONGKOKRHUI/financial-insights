# Endpoints

!!! success "Live"
    All endpoints below are live at `https://finsight-api.onrender.com`.
    Public market-data endpoints are open.
    `POST /search` requires a paid/admin session or API key.

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

**Authentication**

- Session cookie (`access_token`) for signed-in `paid` or `admin` users, or
- `X-API-Key: fsk_...` for paid/admin API access.

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
| 401    | Missing/invalid session or API key     |
| 403    | Authenticated but role is not paid/admin |
| 404    | Ticker not found                       |
| 422    | Invalid `statement_type` value         |

---

## Covered Tickers

The following ticker symbols are valid for all endpoints:

| Ticker    | Company                    | Sector                     |
|-----------|----------------------------|----------------------------|
| MAYBANK   | Malayan Banking Berhad     | Financials                 |
| CIMB      | CIMB Group Holdings Berhad | Financials                 |
| TNB       | Tenaga Nasional Berhad     | Utilities                  |
| PETRONAS  | Petroliam Nasional Berhad  | Energy                     |
| MAXIS     | Maxis Berhad               | Communication Services     |
| TELEKOM   | Telekom Malaysia Berhad    | Communication Services     |
| GENTING   | Genting Berhad             | Consumer Discretionary     |
| SUNWAY    | Sunway Berhad              | Real Estate                |
