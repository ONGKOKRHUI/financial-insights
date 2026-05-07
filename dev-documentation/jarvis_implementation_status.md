# Jarvis Implementation Status

## Purpose
This document records what has already been implemented for Jarvis and what is still pending.

---

## Completed Implementation

### 1) Intent Engine Architecture
- `JARVIS_INTENT_ENGINE` strategy is implemented with three modes:
  - `langgraph` (primary)
  - `keyword` (fallback)
  - `dify` (legacy compatibility)
- Engine-level fallback behavior is implemented in `src/backend/services/jarvis_intent.py`.

### 2) LangGraph Pipeline (Core Flow)
- LangGraph pipeline is implemented in `src/backend/services/langgraph_intent.py`.
- Flow is wired as:
  - `refine_transcript`
  - `classify_intent`
  - route by `intent_id`
  - intent-specific handler output
- Structured output schema is implemented via Pydantic (`IntentOutput`, `IntentEntities`).

### 2.1) LangGraph Design View (Handover Reference)
This is the design-level view from `.cursor/plans/langgraph_intent_engine_35044f04.plan.md` so another engineer can step in quickly.

```mermaid
flowchart TD
    START([START]) --> refine_transcript
    refine_transcript --> classify_intent
    classify_intent --> route_intent{intent_id?}
    route_intent -->|"1 - Navigation"| handle_navigation
    route_intent -->|"2 - FinancialInfo"| handle_financial
    route_intent -->|"3 - CompanyInfo"| handle_company_info
    route_intent -->|"4 - Documentation"| handle_documentation
    route_intent -->|"5 - SmallTalk"| handle_small_talk
    route_intent -->|"6 - default"| handle_sensitive
    handle_navigation --> endNode([END])
    handle_financial --> endNode
    handle_company_info --> endNode
    handle_documentation --> endNode
    handle_small_talk --> endNode
    handle_sensitive --> endNode
```

State contract used by the graph:
- `raw_transcript`
- `session_id`
- `refined_text`
- `intent_id`
- `intent_name`
- `confidence`
- `entities` (company, metric, time_period, navigation_target)
- `reasoning`
- `output` (final branch response)

Node responsibilities:
- `refine_transcript`: clean STT artifacts before classification.
- `classify_intent`: structured classification to one of six intents.
- `handle_navigation`: build route payload for company/page navigation.
- `handle_financial`: currently placeholder (main unfinished branch).
- `handle_company_info`: resolve company context and respond with grounded info.
- `handle_documentation`: retrieve docs context (RAG + file fallback) and respond.
- `handle_small_talk`: conversational branch.
- `handle_sensitive`: safe refusal branch.

Unified output schema returned to router/frontend:
- `action`: `"navigate"` or `"respond"`
- `target`: route path or `null`
- `message`: UI text response
- `voice`: TTS-friendly response
- `intent_id`: numeric intent
- `refined_transcript`: corrected transcript
- `sources`: citations list
- `confidence`: confidence score
- `engine`: `"langgraph"`

### 3) Implemented Intents
- **Intent 1: Navigation** - implemented (`handle_navigation`)
  - Maps company/entity to frontend route.
  - Returns navigation action payload.
- **Intent 3: Company Information** - implemented (`handle_company_info`)
  - Uses direct database lookup for company profile and related KPI context.
  - Falls back gracefully when context is unavailable.
- **Intent 4: Documentation** - implemented (`handle_documentation`)
  - Uses RAG + file-based documentation fallback.
  - Supports docs extraction flow from API docs sources.
- **Intent 5: Small Talk** - implemented (`handle_small_talk`)
  - Uses dedicated small-talk prompt and response style.
- **Intent 6: Sensitive Topic** - implemented (`handle_sensitive`)
  - Returns refusal/safe response behavior.

### 4) RAG Foundation for Jarvis
- RAG endpoint is implemented in `src/backend/routers/rag.py`:
  - `POST /rag/ask`
  - `GET /rag/health`
- Retrieval and answer generation services are wired (`rag_retriever`, `rag_answer`).
- RAG tests exist in `src/backend/tests/test_rag.py` (happy path, abstention, validation, health, and failures).

### 5) Documentation
- Jarvis documentation pages are present and updated under `docs/ai-systems/`:
  - `jarvis-overview.md`
  - `jarvis-intent-classifier.md`
  - deployment/API reference pages

---

## Completed (continued)

### 6) Intent 2 Extension (FinancialInfo) - **Completed**

`handle_financial` in `src/backend/services/langgraph_intent.py` is fully implemented.

Implementation in `src/backend/services/financial_query.py`:
- `MetricSpec` catalog: 30+ metric aliases across income statement, balance sheet, cash flow, and KPI tables.
- `resolve_ticker()`: normalises company names to canonical KLSE tickers via static alias map + DB fallback.
- `resolve_metric()`: maps natural-language phrases (e.g. "earnings per share", "FCF", "P/E") to `MetricSpec`.
- `parse_fiscal_year()`: parses "FY2024", "last year", "Q3 2024", or `None` (latest available).
- `lookup_financial_metric()`: deterministic PostgreSQL query; no LLM-generated SQL.
- `query_financial_intent()`: top-level entry point called by `handle_financial`.

Source provenance is tracked per metric (`financial_report`, `derived`, `external_market`).
External market metrics (P/E, dividend yield) include a note in the Jarvis response.

### 7) Intent 2 Test Coverage
- 37 tests in `src/backend/tests/test_financial_query.py`.
- Covers: MetricSpec catalog, `resolve_ticker`, `resolve_metric`, `parse_fiscal_year`, `lookup_financial_metric`, `query_financial_intent`, `handle_financial` Jarvis output shape.
- All tests run without a live database.

### 8) Docs Updated for Intent 2
- `docs/ai-systems/jarvis-intent-classifier.md`: Intent 2 entity extraction rules, supported metric table, ambiguity behavior, three new few-shot examples.
- `docs/ai-systems/jarvis-architecture.md`: Intent 2 retrieval lane diagram, retrieval lane comparison table, updated component map.
- `docs/backend/fastapi-architecture.md`: `financial_query` service documented, project structure updated, configuration table expanded.
- `docs/backend/database-schema.md`: source provenance section, new company/metric onboarding procedures.
- `docs/api-reference/endpoints.md`: Jarvis voice API and RAG endpoint documentation added, ticker list expansion note.
- `docs/system-design/data-quality.md`: new company/metric onboarding checklists, source provenance rules, validation rules filled in.

---

## Current Overall Status
- Jarvis architecture and all six intent branches are implemented.
- **Intent 2 (FinancialInfo) is now fully supported** with PostgreSQL retrieval, metric catalog, and 37 tests.
- Future work: Phase B query types (comparisons, multi-year trends); Phase C Elasticsearch for qualitative phrase search and live top-5 suggestions.

