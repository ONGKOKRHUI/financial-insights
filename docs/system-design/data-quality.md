# Data Quality

!!! success "Phase 5 Updated"
    Basic data validation rules are in place from Phase 2. Source provenance tracking and
    onboarding checklists were formalised in Phase 6 (Intent 2 implementation).

---

## Overview

Wrong financial numbers erode user trust immediately. FinSight enforces data quality at three
points: schema validation on ingestion, business-logic checks before DB insert, and a
provenance model that makes the origin of every value explicit.

---

## Validation Rules

### Schema Validation

Pydantic models validate all parsed financial data before database insert.

```python
class IncomeStatementRow(BaseModel):
    revenue_bln: float = Field(gt=0)
    gross_profit_bln: float
    operating_income_bln: float
    net_income_bln: float
    eps: float
    gross_margin_pct: float = Field(ge=0, le=100)
    operating_margin_pct: float
    net_margin_pct: float
    fiscal_year: int = Field(ge=2000, le=2100)
```

### Business Logic Validation

Sanity checks applied before accepting a parsed row:

- `gross_profit_bln <= revenue_bln` — gross profit cannot exceed revenue
- `total_assets_bln >= total_equity_bln` — equity is a subset of assets
- `total_assets_bln ≈ total_liabilities_bln + total_equity_bln` — balance sheet identity
- `free_cash_flow_bln = operating_cash_flow_bln + capital_expenditure_bln` — FCF definition (capex is stored as negative)
- Margin fields must be in `[-100, 100]` range

### Cross-Period Consistency

Checks for anomalous period-over-period changes flag rows for manual review:

- Revenue change > 200% year-over-year triggers a warning
- Net income sign flip (positive to negative) triggers a warning
- Total assets change > 100% year-over-year triggers a warning

---

## Source Provenance

Every financial value has an explicit `source_type` tracked in `services/financial_query.py`:

| source_type | Meaning | Impact on Jarvis response |
|---|---|---|
| `financial_report` | Extracted directly from the annual report | Reported as-is |
| `derived` | Computed from two report values (e.g. gross profit / revenue) | Reported as-is |
| `external_market` | Requires live stock price (e.g. P/E = stock price / EPS) | Jarvis adds a note: "based on Market Data and may not reflect live market data" |

When adding new metrics, the `source_type` must be set correctly so users are not misled
about the accuracy of market-derived figures.

---

## New Company Onboarding Checklist

When adding a new KLSE company:

- [ ] Verify the ticker is the official KLSE ticker symbol
- [ ] Confirm all monetary values are in MYR billions unless otherwise noted
- [ ] Provide at least 1 fiscal year of data per financial table
- [ ] Verify balance sheet identity: `total_assets ≈ total_liabilities + total_equity`
- [ ] Verify FCF: `free_cash_flow ≈ operating_cash_flow + capital_expenditure`
- [ ] Mark `pe_ratio` and `dividend_yield_pct` as `None` if live market price is unavailable (e.g. unlisted/private companies)
- [ ] Add the ticker and common spoken aliases to `COMPANY_ALIASES` in `financial_query.py`
- [ ] Add the company to the `_ROUTE_MAP` in `langgraph_intent.py` for navigation support
- [ ] Add seed data to `data/mock_data.py` or insert via migration script
- [ ] Run `tests/test_financial_query.py` and `tests/test_api.py` to confirm existing tests pass

---

## New Metric Onboarding Checklist

When adding a new financial metric:

- [ ] Decide: stored value, derived value, or external market data?
- [ ] Stored value in an existing table: add column via Alembic migration
- [ ] New domain (e.g. live stock price): create a new table rather than overloading `kpi_summaries`
- [ ] Add `MetricSpec` entry to `METRIC_CATALOG` with all natural-language aliases, unit, and `source_type`
- [ ] Add all aliases to `_ALIAS_TO_METRIC`
- [ ] Update seed data in `data/mock_data.py` for all 8 existing companies
- [ ] Write tests covering alias resolution, value formatting, and edge cases (null value, missing row)
- [ ] Update `docs/backend/database-schema.md` and `docs/api-reference/endpoints.md`
- [ ] Update `docs/ai-systems/jarvis-intent-classifier.md` to list the new metric in the supported metrics table

---

## Quality Monitoring

!!! info "Planned Architecture (Future Phases)"
    Automated quality dashboards and per-intent retrieval monitoring are planned for Phase 6.

Metrics to track:

- **Completeness** — percentage of expected (ticker, fiscal_year) pairs that have rows in each table
- **Validation failure rate** — number of rejected rows per ingestion run
- **Null rate per column** — tracks `pe_ratio`, `dividend_yield_pct`, and other nullable fields
- **Intent 2 answer quality** — percentage of financial queries that return `found=True` vs. fallback

---

## Dead Letter Handling

Failed or rejected financial records should be stored in a `dead_letter_queue` table with:

- `source_pdf_path` — origin file
- `rejection_reason` — validation error message
- `raw_data_json` — original parsed values
- `created_at` — timestamp for review prioritisation

Manual review resolves edge cases (unusual reporting formats, restatements, currency changes).

---

## Data Freshness

Freshness SLA targets:

- Annual report filings ingested within 48 hours of Bursa Malaysia disclosure
- KPI summaries updated after each filing ingestion
- Market-derived values (P/E, dividend yield) updated separately from report ingestion
