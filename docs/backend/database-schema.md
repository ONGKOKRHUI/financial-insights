# Database Schema

!!! success "Phase 4 Updated"
    The core PostgreSQL schema for companies and financials was designed in
    Phase 2.  Phase 4 adds three new tables: ``users``, ``refresh_tokens``,
    and ``api_keys`` for authentication and RBAC.

---

## Entity Relationship Overview

```mermaid
erDiagram
    COMPANIES {
        int id PK
        string ticker UK
        string name
        string sector
        string industry
        text description
        float market_cap_bln
        int employees
        int founded
        string headquarters
        string website
        string currency
        string exchange
    }
    KPI_SUMMARIES {
        int id PK
        string ticker FK
        int fiscal_year
        float revenue_bln
        float net_income_bln
        float eps
        float pe_ratio
        float roe_pct
        float debt_to_equity
    }
    INCOME_STATEMENTS {
        int id PK
        string ticker FK
        int fiscal_year
        float revenue_bln
        float gross_profit_bln
        float operating_income_bln
        float net_income_bln
        float eps
        float gross_margin_pct
    }
    BALANCE_SHEETS {
        int id PK
        string ticker FK
        int fiscal_year
        float total_assets_bln
        float total_liabilities_bln
        float total_equity_bln
        float cash_and_equivalents_bln
        float total_debt_bln
    }
    CASH_FLOWS {
        int id PK
        string ticker FK
        int fiscal_year
        float operating_cash_flow_bln
        float capital_expenditure_bln
        float free_cash_flow_bln
        float dividends_paid_bln
    }
    QUALITATIVE_INSIGHTS {
        int id PK
        string ticker FK
        int fiscal_year
        text future_outlook
        text key_strategic_events
    }
    USERS {
        int id PK
        string email UK
        string hashed_password
        string role
        string stripe_customer_id
        string stripe_subscription_id
        bool is_active
        datetime created_at
    }
    REFRESH_TOKENS {
        int id PK
        int user_id FK
        string token_hash UK
        datetime expires_at
        bool revoked
    }
    API_KEYS {
        int id PK
        int user_id FK
        string key_hash UK
        string key_prefix
        datetime created_at
        bool revoked
    }

    COMPANIES ||--o{ KPI_SUMMARIES : has
    COMPANIES ||--o{ INCOME_STATEMENTS : has
    COMPANIES ||--o{ BALANCE_SHEETS : has
    COMPANIES ||--o{ CASH_FLOWS : has
    COMPANIES ||--o{ QUALITATIVE_INSIGHTS : has
    USERS ||--o{ REFRESH_TOKENS : owns
    USERS ||--o{ API_KEYS : owns
```

---

## Tables

### `companies`

Central reference table.  All financial statement tables use `ticker` as a
foreign key rather than a numeric `company_id`, which simplifies queries and
API routing.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Auto-increment |
| `ticker` | `VARCHAR(20) UNIQUE` | Exchange ticker (e.g. `MAYBANK`) |
| `name` | `VARCHAR(200)` | Full company name |
| `sector` / `industry` | `VARCHAR(100)` | GICS classification |
| `description` | `TEXT` | Company overview |
| `market_cap_bln` | `FLOAT` | Market cap in MYR billions |
| `employees` | `INTEGER` | Approximate headcount |
| `currency` | `VARCHAR(10)` | Default `MYR` |
| `exchange` | `VARCHAR(50)` | Default `KLSE` |

### `kpi_summaries`

One row per `(ticker, fiscal_year)`.  Unique constraint enforced.

| Column | Type | Notes |
|---|---|---|
| `revenue_bln` | `FLOAT` | Total revenue in MYR billions |
| `eps` | `FLOAT` | Earnings per share |
| `pe_ratio` | `FLOAT` | Nullable — not available for all companies |
| `roe_pct` | `FLOAT` | Return on equity % |
| `debt_to_equity` | `FLOAT` | Total debt / total equity |

### `income_statements`

One row per `(ticker, fiscal_year)`.

| Column | Type | Notes |
|---|---|---|
| `gross_margin_pct` | `FLOAT` | Computed: gross_profit / revenue × 100 |
| `operating_margin_pct` | `FLOAT` | Computed |
| `net_margin_pct` | `FLOAT` | Computed |

### `balance_sheets`

One row per `(ticker, fiscal_year)`.  All values in MYR billions.

### `cash_flows`

One row per `(ticker, fiscal_year)`.  `free_cash_flow_bln` = operating − capex.

### `qualitative_insights`

One row per `(ticker, fiscal_year)`.  `key_strategic_events` is stored as a
JSON string and parsed by the router before returning to the client.

---

## Auth Tables (Phase 4)

### `users`

Registered accounts.

| Column | Type | Notes |
|---|---|---|
| `email` | `VARCHAR(255) UNIQUE` | Indexed; login identifier |
| `hashed_password` | `VARCHAR(255)` | bcrypt hash (via passlib) |
| `role` | `VARCHAR(20)` | `free` \| `paid` \| `admin`; default `free` |
| `stripe_customer_id` | `VARCHAR(100)` | Nullable; set when Stripe customer is created |
| `stripe_subscription_id` | `VARCHAR(100)` | Nullable; set when subscription is active |
| `is_active` | `BOOLEAN` | Soft-disable without deleting; default `true` |
| `created_at` | `DATETIME` | UTC timestamp |

### `refresh_tokens`

Long-lived tokens persisted as hashes for server-side revocation.

| Column | Type | Notes |
|---|---|---|
| `user_id` | `INTEGER FK → users.id` | `ON DELETE CASCADE` |
| `token_hash` | `VARCHAR(255) UNIQUE` | SHA-256 hex of the raw JWT string |
| `expires_at` | `DATETIME` | 7 days after creation |
| `revoked` | `BOOLEAN` | Set to `true` on logout |

### `api_keys`

Developer API keys for programmatic access (paid/admin tier).

| Column | Type | Notes |
|---|---|---|
| `user_id` | `INTEGER FK → users.id` | `ON DELETE CASCADE` |
| `key_hash` | `VARCHAR(64) UNIQUE` | SHA-256 hex of the raw `fsk_…` key |
| `key_prefix` | `VARCHAR(10)` | First 8 chars — safe to display in UI |
| `revoked` | `BOOLEAN` | Set to `true` on rotation or downgrade |

---

## Migrations (Alembic)

Phase 4 introduces Alembic for database migrations.

**Setup:**
```bash
cd src/backend
alembic upgrade head
```

**Creating a new migration:**
```bash
alembic revision --autogenerate -m "describe_the_change"
alembic upgrade head
```

**Rolling back one step:**
```bash
alembic downgrade -1
```

Migration files are stored in `src/backend/alembic/versions/`.  The initial
Phase 4 migration is `001_add_auth_tables.py`.

---

## pgvector Setup (Phase 5)

Vector search for RAG will be added in Phase 5.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE INDEX ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```
