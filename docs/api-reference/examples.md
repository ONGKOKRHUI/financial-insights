# Usage Examples

!!! success "Phase 3 — Live"
    All examples below use the live production API. No API key is required.

---

## Quick Start

=== "curl"
    ```bash
    curl "https://finsight-api.onrender.com/companies"
    ```

=== "Python"
    ```python
    import httpx

    res = httpx.get("https://finsight-api.onrender.com/companies")
    companies = res.json()
    print(companies[0]["ticker"])  # "MAYBANK"
    ```

=== "JavaScript"
    ```javascript
    const res = await fetch("https://finsight-api.onrender.com/companies");
    const companies = await res.json();
    console.log(companies[0].ticker); // "MAYBANK"
    ```

---

## Fetch a KPI Summary

=== "curl"
    ```bash
    curl "https://finsight-api.onrender.com/companies/MAYBANK/summary"
    ```

=== "Python"
    ```python
    res = httpx.get("https://finsight-api.onrender.com/companies/MAYBANK/summary")
    kpi = res.json()
    print(f"ROE: {kpi['roe_pct']}%  |  Dividend yield: {kpi['dividend_yield_pct']}%")
    ```

=== "JavaScript"
    ```javascript
    const res = await fetch("https://finsight-api.onrender.com/companies/MAYBANK/summary");
    const kpi = await res.json();
    console.log(`ROE: ${kpi.roe_pct}%  |  Fiscal year: ${kpi.fiscal_year}`);
    ```

---

## Fetch an Income Statement

=== "curl"
    ```bash
    curl "https://finsight-api.onrender.com/financials/MAYBANK/income-statement"
    ```

=== "Python"
    ```python
    res = httpx.get("https://finsight-api.onrender.com/financials/MAYBANK/income-statement")
    stmt = res.json()
    for year in stmt["data"]:
        print(year["fiscal_year"], year["revenue_bln"], year["net_margin_pct"])
    ```

=== "JavaScript"
    ```javascript
    const res = await fetch("https://finsight-api.onrender.com/financials/MAYBANK/income-statement");
    const stmt = await res.json();
    stmt.data.forEach(y => console.log(y.fiscal_year, y.revenue_bln, y.net_margin_pct));
    ```

---

## POST /search — Unified Query

The `POST /search` endpoint lets you query any statement type with a single,
consistent payload — useful for scripts that need to retrieve different data
types without managing multiple URL patterns.

=== "curl"
    ```bash
    curl -X POST "https://finsight-api.onrender.com/search" \
      -H "Content-Type: application/json" \
      -d '{"ticker": "MAYBANK", "statement_type": "income_statement"}'
    ```

=== "Python"
    ```python
    import httpx

    client = httpx.Client(base_url="https://finsight-api.onrender.com")

    # Latest income statement
    res = client.post("/search", json={
        "ticker": "MAYBANK",
        "statement_type": "income_statement",
    })
    print(res.json()["data"]["revenue_bln"])

    # Specific year
    res = client.post("/search", json={
        "ticker": "CIMB",
        "statement_type": "kpi",
        "fiscal_year": 2023,
    })
    print(res.json()["data"]["roe_pct"])
    ```

=== "JavaScript"
    ```javascript
    const BASE = "https://finsight-api.onrender.com";

    async function search(ticker, statementType, fiscalYear = null) {
      const body = { ticker, statement_type: statementType };
      if (fiscalYear) body.fiscal_year = fiscalYear;

      const res = await fetch(`${BASE}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      return res.json();
    }

    const result = await search("MAYBANK", "income_statement", 2024);
    console.log(result.data.revenue_bln);
    ```

---

## Iterate Over All Companies

=== "Python"
    ```python
    import httpx

    BASE = "https://finsight-api.onrender.com"
    client = httpx.Client()

    companies = client.get(f"{BASE}/companies").json()

    for company in companies:
        ticker = company["ticker"]
        kpi = client.get(f"{BASE}/companies/{ticker}/summary").json()
        print(f"{ticker}: ROE={kpi['roe_pct']}%  EPS={kpi['eps']}")
    ```

=== "JavaScript"
    ```javascript
    const BASE = "https://finsight-api.onrender.com";

    const companies = await fetch(`${BASE}/companies`).then(r => r.json());

    for (const { ticker } of companies) {
      const kpi = await fetch(`${BASE}/companies/${ticker}/summary`).then(r => r.json());
      console.log(`${ticker}: ROE=${kpi.roe_pct}%  EPS=${kpi.eps}`);
    }
    ```

---

## Handle Errors

=== "Python"
    ```python
    res = httpx.get("https://finsight-api.onrender.com/companies/NOTEXIST")
    if res.status_code == 404:
        print(res.json()["detail"])  # "Company 'NOTEXIST' not found."
    ```

=== "JavaScript"
    ```javascript
    const res = await fetch("https://finsight-api.onrender.com/companies/NOTEXIST");
    if (!res.ok) {
      const err = await res.json();
      console.error(err.detail); // "Company 'NOTEXIST' not found."
    }
    ```
