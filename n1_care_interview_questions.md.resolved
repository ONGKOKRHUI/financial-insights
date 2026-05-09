# Questions for n1.care Principal Engineer (Arun Venkataraman)

> **Context:** You (FinSight) and n1.care solve the same core problem in different domains — turning **unstructured PDFs into structured, validated data** and then generating **AI-powered analytical reports**. Their pipeline is more mature (multi-agent reports, parallel extraction, smart routing, canonical naming, deduplication, observability). These questions target the gaps between your current implementation and their production system.

---

## 1. Document Parsing & Classification

### Q1.1 — Page-Level Classification Before Extraction

> *"Your pipeline classifies each page by data type (biomarker results, clinical findings, genetic data) and filters out non-medical content before extraction. How do you implement this classification step — is it a separate LLM call per page, a fine-tuned classifier, or something else? What accuracy do you target for this pre-screening?"*

| | Detail |
|---|---|
| **Purpose** | Understand their approach to intelligent document pre-processing |
| **Answer I'm looking for** | Whether they use a lightweight classifier (e.g. fine-tuned BERT), an LLM call, or vision model for page classification; what accuracy threshold they require |
| **How it helps FinSight** | Your `router.py` currently passes the **entire document** to both branches unchanged — no filtering, no classification. Financial reports contain dozens of irrelevant pages (corporate governance, director profiles, photos). Pre-classifying pages would reduce token cost and improve extraction accuracy |
| **Which part it fixes** | [router.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/router.py) — the node that should intelligently route content but currently just copies everything |

### Q1.2 — Vision Models for Scanned / Complex Tables

> *"You mention routing visually complex pages (charts, scanned tables) to specialised vision models while text-heavy pages use faster text models. What vision models are you using, and how do you decide the routing threshold?"*

| | Detail |
|---|---|
| **Purpose** | Learn their multi-modal routing strategy |
| **Answer I'm looking for** | Specific models (GPT-4V, Gemini Vision, custom), routing heuristics (OCR confidence score, image-to-text ratio), and latency trade-offs |
| **How it helps FinSight** | Your parser uses LlamaParse for everything or falls back to PyMuPDF plain text. Malaysian financial PDFs often contain scanned tables, watermarked pages, and complex multi-column layouts that lose structure in text-only extraction |
| **Which part it fixes** | [parser.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/parser.py) — single-path parsing with no visual intelligence |

### Q1.3 — OCR Strategy for Non-Digital PDFs

> *"For scanned documents and handwritten notes, what OCR pipeline do you use? Do you pre-process images (deskew, denoise) before OCR, or does the VLM handle that natively?"*

| | Detail |
|---|---|
| **Purpose** | Understand production OCR best practices |
| **Answer I'm looking for** | Whether they use Tesseract, Google Document AI, Azure Form Recognizer, or VLMs directly; any pre-processing steps |
| **How it helps FinSight** | Some Bursa Malaysia quarterly reports are scanned PDFs. PyMuPDF returns empty text for these, and LlamaParse quality varies. A robust OCR fallback strategy would increase coverage |
| **Which part it fixes** | [parser.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/parser.py) — `_pymupdf_fallback` returns empty strings for scanned PDFs |

---

## 2. Parallel Extraction Architecture

### Q2.1 — Parallel Processor Design

> *"You run four specialised AI processors in parallel for different data categories. Are these separate LLM calls with different prompts, fine-tuned models, or entirely different model architectures? How do you manage the fan-out/fan-in coordination?"*

| | Detail |
|---|---|
| **Purpose** | Understand their parallel extraction architecture at a deep level |
| **Answer I'm looking for** | Whether each processor is a prompted LLM, a fine-tuned model, or a mix; what orchestration framework they use (LangGraph, Prefect, custom); how they handle partial failures |
| **How it helps FinSight** | Your pipeline runs 4 sequential LLM calls inside `extract_quantitative` (income statement → balance sheet → cash flow → KPI) which is slow. Their approach of true parallel processing could cut extraction time by 3-4x |
| **Which part it fixes** | [quantitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/quantitative.py#L218-L226) — the sequential `for` loop over statement types |

### Q2.2 — Handling Partial Failures in Parallel Branches

> *"When one of your four parallel processors fails but the others succeed, how do you handle that? Do you retry just the failed branch, degrade gracefully, or fail the whole document?"*

| | Detail |
|---|---|
| **Purpose** | Learn resilience patterns for parallel AI pipelines |
| **Answer I'm looking for** | Retry strategy (per-branch vs whole pipeline), circuit breakers, degraded output handling |
| **How it helps FinSight** | Your `merger.py` handles partial failures but your quantitative node doesn't retry individual statement extractions. If the balance sheet extraction fails, you lose all KPI data too since it's in the same sequential loop |
| **Which part it fixes** | [quantitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/quantitative.py) and [merger.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/merger.py) — no per-statement retry logic |

---

## 3. Data Standardisation & Enrichment

### Q3.1 — Canonical Naming with Medical Embedding Models

> *"You use medical embedding models to cluster similar biomarker names under a single canonical name. What embedding model do you use, and how did you build the clustering? Is it a static lookup table, dynamic similarity matching, or a trained classifier?"*

| | Detail |
|---|---|
| **Purpose** | Learn how they solve the entity resolution / normalisation problem |
| **Answer I'm looking for** | Specific embedding model, similarity threshold, whether it's offline (pre-built mapping) or online (real-time clustering) |
| **How it helps FinSight** | Malaysian financial reports use inconsistent terminology across companies: "Revenue" vs "Turnover" vs "Total Income", "PAT" vs "Net Profit" vs "Profit After Tax". Your pipeline relies on the LLM to understand these synonyms in the prompt, but has no explicit normalisation layer |
| **Which part it fixes** | [quantitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/quantitative.py#L103-L131) — `_EXTRACTION_PROMPT` relies on LLM intelligence to resolve naming; [schemas.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/schemas.py) — rigid field names with no synonym resolution |

### Q3.2 — Unit Conversion Strategy

> *"You standardise units across providers so values are directly comparable. How do you handle ambiguous units — e.g., when a lab doesn't specify the unit, or uses a non-standard format? Do you use rules, LLM inference, or reference databases?"*

| | Detail |
|---|---|
| **Purpose** | Understand their approach to unit normalisation edge cases |
| **Answer I'm looking for** | Whether they use a rule-based system, LLM inference, or clinical reference databases; how they handle missing units |
| **How it helps FinSight** | Your `_unit_multiplier()` function uses regex-based rules but has edge cases: some Malaysian reports state "RM" without specifying thousands/millions, some use "MYR" vs "RM" inconsistently. The function falls back to "no multiplier" on unrecognised headers which silently produces wrong values |
| **Which part it fixes** | [quantitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/quantitative.py#L267-L298) — `_unit_multiplier` regex rules and silent fallback |

---

## 4. Deduplication & Temporal Intelligence

### Q4.1 — Cross-Page Deduplication

> *"You automatically detect and merge duplicate entries across pages. What's your deduplication strategy — exact match, fuzzy match, or embedding similarity? How do you decide which version to keep?"*

| | Detail |
|---|---|
| **Purpose** | Learn production deduplication patterns for extracted data |
| **Answer I'm looking for** | Matching algorithm, conflict resolution strategy (most complete, most recent, highest confidence) |
| **How it helps FinSight** | Your pipeline has **no deduplication**. Financial reports often repeat the same numbers in summaries, highlights, and detailed statements. The LLM might extract slightly different values from different sections of the same report, and there's no reconciliation |
| **Which part it fixes** | Missing entirely — should be added between extraction and merge in [merger.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/merger.py) |

### Q4.2 — Intelligent Date Inference

> *"When test dates are missing from a page, you propagate dates from adjacent pages. How does this work technically — is it a post-processing rule engine or part of the extraction model?"*

| | Detail |
|---|---|
| **Purpose** | Understand temporal context propagation across document pages |
| **Answer I'm looking for** | Whether it's rule-based (page proximity heuristic) or model-based; how they handle multi-year reports |
| **How it helps FinSight** | Your pipeline extracts `fiscal_year` from the **filename only** (`MAYBANK_2024_Q3.pdf`). If the filename is wrong or if a report contains comparative data from multiple years, the pipeline has no way to disambiguate. Some reports contain both current and prior year figures in the same table |
| **Which part it fixes** | [parser.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/parser.py#L36-L66) — `_extract_metadata_from_path` relies solely on filename convention |

---

## 5. Multi-Agent Report Generation

### Q5.1 — Multi-Agent Architecture

> *"Your Advanced Multi-Perspective Review uses multi-agent AI to provide diverse clinical perspectives. How is this architected — are these separate LLM personas with different system prompts, fine-tuned models, or agents with different tool access? How do you prevent them from contradicting each other?"*

| | Detail |
|---|---|
| **Purpose** | Understand production multi-agent report generation |
| **Answer I'm looking for** | Agent architecture (persona-based prompting vs fine-tuned models vs tool-differentiated agents), consistency/contradiction handling, orchestration framework |
| **How it helps FinSight** | Phase 5 plans a multi-agent system but has no concrete architecture. n1.care's approach to specialist agent perspectives (cardiologist, nephrologist, endocrinologist) maps directly to financial analyst perspectives (equity analyst, credit analyst, macro strategist) |
| **Which part it fixes** | [5_phase-5.md](file:///c:/Users/HP/Documents/repos/financial-insights/dev-documentation/5_phase-5.md) — planned but unimplemented multi-agent system |

### Q5.2 — Evidence Grounding & Citation

> *"Every insight and recommendation in your reports is grounded in the patient's actual data with citations. How do you technically implement this — does the LLM generate citations inline, or do you post-process to verify and add them?"*

| | Detail |
|---|---|
| **Purpose** | Learn how to build verifiable, trustworthy AI outputs |
| **Answer I'm looking for** | Whether citations are generated by the LLM, verified by a separate validation step, or enforced via structured output schemas |
| **How it helps FinSight** | Your `qualitative.py` generates summaries but with **no source attribution**. The `future_outlook` field is a free-text summary with no way to verify which part of the report it came from. For a financial platform, unsourced AI statements are a liability risk |
| **Which part it fixes** | [qualitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/qualitative.py) — no citation or source tracking in extracted insights |

---

## 6. Validation & Quality Assurance

### Q6.1 — Clinical-Grade Validation Pipeline

> *"You validate extracted data against clinical standards. What does your validation pipeline look like — do you use rule-based validators, a second LLM pass, or domain-expert review? What's your target accuracy for extraction?"*

| | Detail |
|---|---|
| **Purpose** | Understand production-grade data validation strategies |
| **Answer I'm looking for** | Multi-layer validation approach (rules → LLM → human), accuracy metrics, how they measure extraction quality |
| **How it helps FinSight** | Your validation is limited to Pydantic schema validation (type checking) and a basic ground-truth comparison script. There's no semantic validation (e.g., "revenue can't be negative", "net margin must be between -100% and 100%", "total assets = total liabilities + equity") |
| **Which part it fixes** | [merger.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/merger.py) — validation is type-only; [validate_extraction_accuracy.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/validation/validate_extraction_accuracy.py) — basic tolerance-based comparison |

### Q6.2 — Human-in-the-Loop Review

> *"Every AI output requires clinician sign-off before reaching patients. How is the review interface designed? Do clinicians see diffs, confidence scores, or flagged sections? What percentage of outputs require manual correction?"*

| | Detail |
|---|---|
| **Purpose** | Understand how to build effective human review workflows |
| **Answer I'm looking for** | UI/UX for review, confidence scoring mechanism, correction rate metrics |
| **How it helps FinSight** | Your pipeline has **zero human-in-the-loop**. Extracted data goes straight from LLM to database. For financial data that investors rely on, this is risky. Adding confidence scores and a review queue would dramatically improve data quality |
| **Which part it fixes** | Missing entirely — no review workflow exists between pipeline output and database insertion in [loader.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/db/loader.py) |

---

## 7. Model Selection & Prompt Engineering

### Q7.1 — Model Selection for Different Tasks

> *"You route different content types to different models (vision models for charts, text models for text-heavy pages). What models are you using for each task — extraction, classification, report generation? Have you evaluated open-source vs proprietary models?"*

| | Detail |
|---|---|
| **Purpose** | Get concrete model recommendations for different pipeline stages |
| **Answer I'm looking for** | Specific models per task, evaluation methodology, cost/accuracy trade-offs |
| **How it helps FinSight** | You use Gemini 2.0 Flash for everything — extraction, qualitative analysis, and the Jarvis intent system. Different tasks may benefit from different models (e.g., a cheaper model for classification, a stronger model for complex table extraction) |
| **Which part it fixes** | [quantitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/quantitative.py#L82-L87) and [qualitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/qualitative.py#L48-L53) — both hardcode `gemini-2.0-flash` |

### Q7.2 — Structured Output Reliability

> *"When using LLMs for structured data extraction, how do you ensure the output schema is consistently followed? Do you use function calling, JSON mode, retry with correction, or constrained decoding?"*

| | Detail |
|---|---|
| **Purpose** | Learn techniques for reliable structured LLM outputs |
| **Answer I'm looking for** | Specific techniques (function calling, constrained generation, retry loops with error feedback), failure rates |
| **How it helps FinSight** | Your pipeline uses `with_structured_output()` from LangChain which wraps function calling, but has no retry-with-correction logic. If the LLM returns malformed data, the entire statement extraction fails silently |
| **Which part it fixes** | [quantitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/quantitative.py#L162-L197) — `_extract_statement` catches exceptions but doesn't retry |

---

## 8. Observability & Reliability

### Q8.1 — Pipeline Observability Stack

> *"You mention comprehensive observability — what does your observability stack look like? Do you track per-stage latency, token usage, extraction confidence, and error rates? What tools do you use?"*

| | Detail |
|---|---|
| **Purpose** | Learn production observability patterns for AI pipelines |
| **Answer I'm looking for** | Specific tools (Langfuse, Datadog, custom), what metrics they track, alerting strategy |
| **How it helps FinSight** | You have Langfuse callbacks wired up but minimal observability beyond that. No per-stage latency tracking, no cost dashboards, no extraction confidence metrics. Phase 5 plans observability but lacks specifics |
| **Which part it fixes** | All pipeline nodes — Langfuse is wired but not measuring meaningful metrics; [5_phase-5.md](file:///c:/Users/HP/Documents/repos/financial-insights/dev-documentation/5_phase-5.md) — planned but vague observability goals |

### Q8.2 — Retry, Recovery & Idempotency

> *"You mention automatic retry and recovery in your pipeline. How do you implement this — is it at the pipeline level, per-stage, or per-API-call? How do you ensure idempotency when retrying?"*

| | Detail |
|---|---|
| **Purpose** | Understand production retry/recovery patterns |
| **Answer I'm looking for** | Retry granularity, backoff strategy, idempotency keys, dead-letter queues |
| **How it helps FinSight** | Your Dify client has retry logic (3 retries with linear backoff) but the LangGraph pipeline has **no retry mechanism**. If a Gemini API call fails mid-pipeline, the entire pipeline fails. Airflow retries the whole DAG task (re-processing everything from scratch) |
| **Which part it fixes** | [graph.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/graph.py) — no per-node retry; [finsight_etl_dag.py](file:///c:/Users/HP/Documents/repos/financial-insights/dags/finsight_etl_dag.py) — retries at task level (too coarse) |

---

## 9. Scale & Performance

### Q9.1 — Throughput and Batch Processing

> *"You support batch upload of entire patient histories. How do you handle batch processing at scale — is it queue-based, event-driven, or scheduled? What's your typical throughput (documents per hour)?"*

| | Detail |
|---|---|
| **Purpose** | Understand production batch processing architecture |
| **Answer I'm looking for** | Queue system (Redis, SQS, Celery), concurrency model, throughput numbers |
| **How it helps FinSight** | Your pipeline processes PDFs **one at a time sequentially** in the Airflow DAG. With 8 companies × ~20 quarterly reports each, batch processing is critical. There's no queue, no concurrency, and no progress tracking |
| **Which part it fixes** | [finsight_etl_dag.py](file:///c:/Users/HP/Documents/repos/financial-insights/dags/finsight_etl_dag.py#L98-L123) — sequential `for pdf_path in unprocessed` loop |

### Q9.2 — Cost Optimisation

> *"Running multi-stage AI pipelines with vision models is expensive. How do you manage API costs — caching, tiered model selection, token budgeting? What does the unit economics look like per document?"*

| | Detail |
|---|---|
| **Purpose** | Learn cost management for AI-heavy pipelines |
| **Answer I'm looking for** | Caching strategy, cost per document, model tier selection logic, token budget enforcement |
| **How it helps FinSight** | You send the **full document** (often 100+ pages) to each of 4 LLM calls plus qualitative extraction. No caching, no token budgeting. A single Maybank annual report costs significant API credits. Pre-classification could eliminate 60-70% of tokens |
| **Which part it fixes** | [router.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/router.py) — sends full document to every branch; no caching layer exists anywhere |

---

## 10. Security & Data Architecture

### Q10.1 — Data Architecture for Longitudinal Tracking

> *"You track biomarker trends over time across multiple providers. What does your data model look like for longitudinal data — is it a time-series schema, an event-sourced model, or a traditional relational schema?"*

| | Detail |
|---|---|
| **Purpose** | Understand their data model for temporal financial/clinical data |
| **Answer I'm looking for** | Schema design, how they handle data versioning, how they link records across time periods |
| **How it helps FinSight** | Your database schema is flat — one row per company per fiscal year per statement type. There's no versioning (if you re-extract, old data is overwritten via upsert), no audit trail, and no way to track how extracted values change across pipeline runs |
| **Which part it fixes** | [models.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/backend/models.py) — flat schema with upsert-on-conflict; [loader.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/db/loader.py) — `ON CONFLICT DO UPDATE` overwrites without history |

### Q10.2 — Access Controls & Audit Logging

> *"You log every authentication event and data access with a full audit trail. What are you using for this — application-level logging, database triggers, or a dedicated audit service?"*

| | Detail |
|---|---|
| **Purpose** | Learn production audit logging patterns |
| **Answer I'm looking for** | Implementation approach (app-level middleware, DB triggers, event bus), storage, querying |
| **How it helps FinSight** | Phase 4 added auth/RBAC but has **no audit logging**. For a financial data platform, tracking who accessed what data and when is essential for compliance and debugging |
| **Which part it fixes** | [auth/dependencies.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/backend/auth/dependencies.py) — auth checks exist but no access logging |

---

## 11. RAG & Agentic System (For Phase 5 Planning)

### Q11.1 — RAG Architecture for Report Generation

> *"Your reports cite sources and explain reasoning. Are you using a RAG pipeline to retrieve relevant data before generation, or is all the data passed directly to the LLM? If RAG, what's your retrieval strategy — vector search, keyword, hybrid?"*

| | Detail |
|---|---|
| **Purpose** | Get concrete RAG architecture guidance for Phase 5 |
| **Answer I'm looking for** | RAG vs direct context injection, retrieval strategy, chunk size, embedding model |
| **How it helps FinSight** | Phase 5 plans pgvector + Elasticsearch hybrid search but the architecture is theoretical. Understanding n1.care's production RAG setup would provide a proven blueprint |
| **Which part it fixes** | [5_phase-5.md](file:///c:/Users/HP/Documents/repos/financial-insights/dev-documentation/5_phase-5.md) — planned RAG with no concrete architecture |

### Q11.2 — Agent Tool Design

> *"If your agents have tool-use capabilities, how do you design the tool interfaces? Do you use function calling, MCP, or custom tool abstractions? How do you prevent the agent from misusing tools?"*

| | Detail |
|---|---|
| **Purpose** | Learn production agent tool design for Phase 5 |
| **Answer I'm looking for** | Tool abstraction layer, guardrails against misuse, tool selection strategy |
| **How it helps FinSight** | Phase 5 plans MCP tools for SQL queries and vector store retrieval. Without guardrails, an agent writing arbitrary SQL against a production database is dangerous |
| **Which part it fixes** | [5_phase-5.md](file:///c:/Users/HP/Documents/repos/financial-insights/dev-documentation/5_phase-5.md) — planned MCP tools with no safety design |

---

## 12. General Engineering & Lessons Learned

### Q12.1 — Biggest Technical Mistakes

> *"Looking back, what's the biggest technical mistake or architectural decision you'd change in your pipeline? What did you learn the hard way?"*

| | Detail |
|---|---|
| **Purpose** | Avoid repeating their mistakes |
| **Answer I'm looking for** | Honest retrospective on early design decisions that didn't scale |
| **How it helps FinSight** | Your project is still early enough to course-correct. Their hindsight could save weeks of rework |
| **Which part it fixes** | Overall architecture decisions |

### Q12.2 — Evaluation & Testing Strategy

> *"How do you evaluate your pipeline's extraction quality at scale? Do you have a ground-truth dataset, automated regression tests, or LLM-as-judge evaluation?"*

| | Detail |
|---|---|
| **Purpose** | Learn how to build a proper evaluation framework |
| **Answer I'm looking for** | Evaluation methodology, dataset size, automation level, metrics tracked |
| **How it helps FinSight** | Your validation is a single `validate_extraction_accuracy.py` script that compares against a small ground-truth JSON. No automated regression tests, no LLM-as-judge, no continuous monitoring of extraction quality |
| **Which part it fixes** | [validate_extraction_accuracy.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/validation/validate_extraction_accuracy.py) — minimal validation framework; [tests/](file:///c:/Users/HP/Documents/repos/financial-insights/tests) — no extraction regression tests |

---

## Quick Reference: Priority Ranking

| Priority | Question | Impact on FinSight |
|---|---|---|
| 🔴 Critical | Q2.1 Parallel Extraction | 3-4x speed improvement |
| 🔴 Critical | Q1.1 Page Classification | 60-70% token cost reduction |
| 🔴 Critical | Q6.1 Validation Pipeline | Data quality / trust |
| 🟠 High | Q3.1 Canonical Naming | Cross-company data consistency |
| 🟠 High | Q4.1 Deduplication | Extraction accuracy |
| 🟠 High | Q5.1 Multi-Agent Architecture | Phase 5 blueprint |
| 🟠 High | Q12.2 Evaluation Strategy | Quality assurance |
| 🟡 Medium | Q7.1 Model Selection | Cost optimisation |
| 🟡 Medium | Q8.1 Observability | Production readiness |
| 🟡 Medium | Q5.2 Evidence Grounding | Trust / liability |
| 🟡 Medium | Q9.2 Cost Optimisation | Operational expense |
| 🟢 Nice-to-have | Q10.1 Data Architecture | Schema evolution |
| 🟢 Nice-to-have | Q11.2 Agent Tool Design | Phase 5 safety |
| 🟢 Nice-to-have | Q12.1 Biggest Mistakes | Strategic advice |
