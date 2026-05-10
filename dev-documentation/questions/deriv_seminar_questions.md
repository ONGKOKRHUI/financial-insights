# Questions for Deriv AI Engineers — "No Proof of Concept" Seminar

> **Session:** *No Proof of Concept: What it Takes to Ship Production AI*
> **Date:** 8 May 2026
>
> **Context:** Deriv is an AI-first fintech company (online trading, est. 1999) with ~300 engineers working across Software 1.0 (traditional), 2.0 (ML), and 3.0 (LLM orchestration). They run production AI across trading, compliance, customer support, and security. Their "Amy" AI agent handles ~70% of customer support tickets, with a "Sentinel" watcher layer for human escalation. They publish lessons on their **Deriv>ed** Substack.
>
> **Why this matters for FinSight:** You're building a production AI pipeline that extracts structured financial data from PDFs (LangGraph + Gemini), serves it via FastAPI, and plans agentic workflows (Phase 5). Deriv has solved many of the same production challenges — shipping AI that actually works, CI/CD for ML, monitoring, autonomous agents — at scale in a regulated fintech environment.

---

## Speakers & What to Ask Each

| Speaker | Role | Topic | Key relevance to FinSight |
|---|---|---|---|
| **Waqas Awan** | SVP of AI | "Automate Everything" strategy | Production AI philosophy, ship-measure-iterate, Doer/Watcher pattern |
| **Daniel Lim** | Monash alumnus | Algorithmic thinking in production AI | CI/CD for ML, testing AI systems, engineering rigour |
| **Johnathan** | 2025 Monash grad, Kaggle Vision champion | **Xforgery** — real-time invoice fraud detection | Document AI, vision models, structured extraction from documents |
| **Ling** | Top Kaggle practitioner | **UX-fix** — autonomous agent for UI PRs | Autonomous agents, GitHub integration, agent tool design |

---

## 1. For Waqas — Production AI Strategy & "Automate Everything"

### Q1.1 — The Ship-Measure-Iterate Cycle

> *"You've talked about the only way to get better at applied AI being to ship, measure, and iterate. When you shipped your first AI system into production at Deriv, what did 'measure' actually look like? What metrics did you track to know if the AI was working, and how did you decide when to iterate vs. when to roll back?"*

| | Detail |
|---|---|
| **Purpose** | Understand how to define "success" for a production AI pipeline |
| **Answer I'm looking for** | Specific metrics (accuracy, latency, cost per inference, business impact), monitoring dashboards, rollback criteria |
| **How it helps FinSight** | Your pipeline has **no production metrics**. You have Langfuse wired up but don't track extraction accuracy over time, cost per PDF, or whether the extracted data actually matches reality. You ship data to the DB with no measurement loop |
| **Which part it fixes** | All pipeline nodes have Langfuse callbacks but no meaningful metrics; [validate_extraction_accuracy.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/validation/validate_extraction_accuracy.py) runs manually, not continuously |

### Q1.2 — The Doer/Watcher Pattern (Amy + Sentinel)

> *"Your Amy Sentinel system decouples the AI 'doer' from a 'watcher' that monitors for regulatory risks, compliance issues, and customer harm. How did you architect this separation? Is the Sentinel a separate model, a rule engine, or another LLM with different instructions? And how do you keep the watcher from becoming a bottleneck?"*

| | Detail |
|---|---|
| **Purpose** | Learn the Doer/Watcher architectural pattern for safe AI deployment |
| **Answer I'm looking for** | Whether Sentinel is rule-based, ML-based, or LLM-based; async vs sync monitoring; alert routing logic; latency impact |
| **How it helps FinSight** | Your pipeline has **zero oversight** — LLM-extracted financial data goes straight into PostgreSQL with no monitoring layer. A Sentinel-style watcher could flag suspicious extractions (e.g., revenue jumping 10x year-over-year, negative total assets) before they corrupt your database |
| **Which part it fixes** | Missing entirely — should exist between [merger.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/merger.py) and [loader.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/db/loader.py). Also relevant to Phase 5's planned AI chatbot needing safety guardrails |

### Q1.3 — When NOT to Use AI

> *"Your philosophy says 'an AI system is only as good as the business problem it actually solves.' In Deriv's 'Automate Everything' initiative, were there cases where you tried AI and it was the wrong tool? How do you decide what to automate with AI vs. traditional software?"*

| | Detail |
|---|---|
| **Purpose** | Understand the decision framework for AI vs. traditional engineering |
| **Answer I'm looking for** | Evaluation criteria (data availability, error tolerance, ROI threshold), examples of AI projects they killed |
| **How it helps FinSight** | Your pipeline uses LLM calls for everything including the `router.py` content routing, which currently just copies the full text to both branches — no AI needed at all. Some parts of your pipeline might be better served by rule-based approaches (e.g., unit conversion, metadata extraction) instead of burning LLM tokens |
| **Which part it fixes** | [router.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/router.py) — does nothing that needs AI; [quantitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/quantitative.py#L267-L298) — `_unit_multiplier` is already rule-based and could be extended instead of relying on LLM |

---

## 2. For Daniel — CI/CD & Engineering Rigour for AI

### Q2.1 — CI/CD Pipeline for AI/ML Systems

> *"Traditional CI/CD tests code correctness, but AI systems can pass all tests and still produce wrong outputs. How does Deriv's CI/CD pipeline handle AI-specific concerns — do you test model outputs, run regression benchmarks, or validate against golden datasets on every deploy?"*

| | Detail |
|---|---|
| **Purpose** | Learn how to build CI/CD that actually catches AI regressions |
| **Answer I'm looking for** | Whether they run model evaluation in CI, golden dataset benchmarks, A/B testing frameworks, canary deployments for models |
| **How it helps FinSight** | Your CI/CD is limited to `python -m compileall .` (syntax checking) and `npx tsc --noEmit` (type checking). There's **no AI-specific CI** — if you change a prompt, update a model version, or modify the extraction logic, there's no automated way to know if extraction quality degraded |
| **Which part it fixes** | [.github/workflows/deploy-backend.yml](file:///c:/Users/HP/Documents/repos/financial-insights/.github/workflows) — only validates Python imports; no extraction quality gates |

### Q2.2 — Testing AI Systems (Beyond Unit Tests)

> *"How do you write tests for non-deterministic AI outputs? If the model gives a slightly different answer each time, how do you define 'correct' and what's your tolerance? Do you use LLM-as-judge, fuzzy matching, or statistical acceptance criteria?"*

| | Detail |
|---|---|
| **Purpose** | Learn practical testing patterns for LLM-based pipelines |
| **Answer I'm looking for** | Testing methodology (deterministic seeding, output range validation, LLM-as-judge, statistical tests), what percentage of failures they tolerate |
| **How it helps FinSight** | Your test suite has `test_pipeline.py` and `test_phase2_extraction.py` but they're integration tests that hit live APIs — not repeatable, not deterministic. Your `validate_extraction_accuracy.py` uses simple absolute tolerance (`tolerance_abs: 0.05`) but this doesn't scale to diverse report formats |
| **Which part it fixes** | [tests/test_pipeline.py](file:///c:/Users/HP/Documents/repos/financial-insights/tests/test_pipeline.py) — live API tests, not reproducible; [validate_extraction_accuracy.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/validation/validate_extraction_accuracy.py) — simplistic tolerance-based validation |

### Q2.3 — Versioning Models, Prompts, and Data Together

> *"When you deploy a new model or update a prompt, how do you version that change alongside the data it was trained/evaluated on? Do you use something like MLflow, DVC, or a custom registry?"*

| | Detail |
|---|---|
| **Purpose** | Understand production model/prompt versioning practices |
| **Answer I'm looking for** | Specific tools (MLflow, Weights & Biases, DVC, custom), how they track prompt→output lineage, rollback strategy |
| **How it helps FinSight** | Your prompts are **hardcoded strings** in Python files with no versioning. If you change `_EXTRACTION_PROMPT` in `quantitative.py`, there's no record of what the previous prompt was, what outputs it produced, or how the new one compares. The `GEMINI_MODEL` env var is the only version control |
| **Which part it fixes** | [quantitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/quantitative.py#L103-L131) — prompts as inline strings; [qualitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/qualitative.py#L70-L98) — same issue; no prompt registry exists |

### Q2.4 — When AI Breaks in Production (Post-Mortems)

> *"On Deriv>ed you publish post-mortems of AI failures. What's the most common failure mode you see in production AI — is it model drift, data distribution shift, prompt brittleness, or something else? How do you detect these before users do?"*

| | Detail |
|---|---|
| **Purpose** | Learn what failure modes to watch for and how to detect them early |
| **Answer I'm looking for** | Common failure patterns, early warning signals, monitoring/alerting setup |
| **How it helps FinSight** | Your pipeline has **no failure detection** beyond catching Python exceptions. If Gemini starts returning slightly wrong numbers (e.g., extracting revenue from the wrong year's column), you'd never know until someone manually checks the database. Financial data errors compound — wrong revenue → wrong margins → wrong analysis |
| **Which part it fixes** | [graph.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/graph.py) — no drift detection; no anomaly alerting anywhere in the pipeline |

---

## 3. For Johnathan — Xforgery (Document AI & Fraud Detection)

### Q3.1 — Document AI Architecture for Invoice Processing

> *"Xforgery detects fraudulent invoices in real time. What's the document processing architecture — do you use OCR first, then a classifier, then extraction? Or do you use end-to-end vision models? How do you handle the variety of invoice formats?"*

| | Detail |
|---|---|
| **Purpose** | Understand a production document AI pipeline from someone who's built one |
| **Answer I'm looking for** | Pipeline stages (OCR → classification → extraction vs. end-to-end VLM), how they handle format variability, model architecture (CNN, ViT, multimodal LLM) |
| **How it helps FinSight** | Your pipeline does PDF → markdown (LlamaParse) → LLM extraction. This is a 2-stage approach. Xforgery's architecture for handling diverse invoice formats maps directly to your challenge of handling 8 different Malaysian company report formats, each with different table layouts and structures |
| **Which part it fixes** | [parser.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/parser.py) — single-path parsing; [quantitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/quantitative.py) — extraction relies entirely on LLM understanding of table structure |

### Q3.2 — Vision Models vs. Text Extraction for Structured Data

> *"As a Kaggle Vision champion — when extracting structured data from documents (like numbers from tables), do you find vision models (processing the document as an image) more reliable than text extraction (OCR → parse)? What are the trade-offs in accuracy, latency, and cost?"*

| | Detail |
|---|---|
| **Purpose** | Get expert opinion on the fundamental approach to document data extraction |
| **Answer I'm looking for** | Comparative analysis of vision-first vs. text-first approaches, specific model recommendations, when to use which |
| **How it helps FinSight** | You're using a text-first approach (PDF → markdown text → LLM). Malaysian financial PDFs have complex multi-column tables, merged cells, and footnotes that lose structure when converted to text. A vision-based approach might extract table data more accurately, but you haven't evaluated this |
| **Which part it fixes** | [parser.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/parser.py) — text-only extraction path; potential new vision-based extraction approach |

### Q3.3 — Real-Time vs. Batch Processing for Document AI

> *"Xforgery works in real time. How did you architect for low latency — is it model optimisation (quantisation, distillation), infrastructure (GPU serving, model caching), or architectural choices (lighter models for screening, heavier models for flagged items)?"*

| | Detail |
|---|---|
| **Purpose** | Learn how to optimise document AI pipeline latency |
| **Answer I'm looking for** | Specific optimisation techniques, tiered model approach, infrastructure decisions |
| **How it helps FinSight** | Your pipeline takes **minutes per PDF** because it makes 5 sequential LLM API calls (4 quantitative + 1 qualitative) on the full document. A tiered approach (fast classifier → targeted extraction) could dramatically reduce latency and cost |
| **Which part it fixes** | [quantitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/quantitative.py#L218-L226) — sequential extraction loop; [router.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/router.py) — no intelligent routing/filtering |

### Q3.4 — Confidence Scoring & Flagging Uncertain Extractions

> *"When Xforgery detects a potentially fraudulent invoice, how do you assign confidence scores? And how did you calibrate the threshold between 'auto-approve' and 'flag for human review'?"*

| | Detail |
|---|---|
| **Purpose** | Learn how to build confidence-based routing for extracted data |
| **Answer I'm looking for** | Confidence scoring method (model logits, ensemble disagreement, rule-based checks), threshold calibration, human review workflow |
| **How it helps FinSight** | Your pipeline has **no confidence scores**. Every extraction is treated as equally reliable, whether the LLM confidently found a value in a clear table or guessed from ambiguous text. Adding confidence scores would let you flag uncertain values for review instead of silently inserting potentially wrong data |
| **Which part it fixes** | [quantitative.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/quantitative.py) — `_extract_statement` returns data with no confidence signal; [merger.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/merger.py) — merges without knowing which values are uncertain |

### Q3.5 — Building and Maintaining Ground Truth Datasets

> *"For Xforgery, how did you build your ground truth dataset of genuine vs. fraudulent invoices? How large is it, and how do you keep it current as fraud patterns evolve?"*

| | Detail |
|---|---|
| **Purpose** | Learn how to build and maintain evaluation datasets for document extraction |
| **Answer I'm looking for** | Dataset creation methodology (manual labelling, synthetic data, production data), size, refresh cadence |
| **How it helps FinSight** | Your ground truth is a **single small JSON file** (`mock_ground_truth.json`). You need a comprehensive ground truth dataset covering all 8 companies across multiple years, but building and maintaining that is a significant effort. Their approach could show shortcuts |
| **Which part it fixes** | [ground_truth/](file:///c:/Users/HP/Documents/repos/financial-insights/ground_truth) — minimal ground truth; [validate_extraction_accuracy.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/validation/validate_extraction_accuracy.py) — validator is ready but starved for data |

---

## 4. For Ling — UX-fix (Autonomous Agents)

### Q4.1 — Agent Architecture for UX-fix

> *"UX-fix autonomously navigates user flows and generates GitHub PRs for UI improvements. What's the agent architecture — is it a single LLM with tools, a multi-agent system with specialised roles, or a planner-executor pattern? What orchestration framework do you use?"*

| | Detail |
|---|---|
| **Purpose** | Learn production autonomous agent architecture for Phase 5 |
| **Answer I'm looking for** | Agent framework (LangGraph, AutoGen, CrewAI, custom), tool design, planning strategy, how the agent decides what to fix |
| **How it helps FinSight** | Phase 5 plans a multi-agent system where AI agents dynamically decide whether to use RAG retrieval or SQL queries. UX-fix is a working example of an autonomous agent with real tool use (browser navigation, code generation, git operations). Their architecture is a proven blueprint |
| **Which part it fixes** | [5_phase-5.md](file:///c:/Users/HP/Documents/repos/financial-insights/dev-documentation/5_phase-5.md) — planned multi-agent system with no concrete architecture |

### Q4.2 — Tool Design & Safety Guardrails for Autonomous Agents

> *"UX-fix generates actual GitHub PRs — that's code changes hitting a real repo. How do you prevent the agent from making harmful changes? What guardrails exist — sandboxed execution, output validation, human approval gates, or rollback mechanisms?"*

| | Detail |
|---|---|
| **Purpose** | Learn safety patterns for agents that take real-world actions |
| **Answer I'm looking for** | Sandboxing strategy, approval workflows, rollback mechanisms, how they limit blast radius |
| **How it helps FinSight** | Phase 5 plans MCP tools that let an AI agent write SQL queries against your production PostgreSQL database. Without guardrails, a hallucinating agent could corrupt financial data. UX-fix solves an analogous problem — autonomous code changes to a real codebase |
| **Which part it fixes** | [5_phase-5.md](file:///c:/Users/HP/Documents/repos/financial-insights/dev-documentation/5_phase-5.md) — planned MCP tools with no safety design; also relevant to [langgraph_intent.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/backend/services/langgraph_intent.py) — the existing LangGraph agent has no guardrails |

### Q4.3 — Agent Evaluation: How Do You Know the Agent is Doing the Right Thing?

> *"How do you evaluate UX-fix's outputs? Do you measure PR quality, merge rate, regression rate? Is there an automated way to test whether the agent's suggested fix actually improves the UI, or does it always require human review?"*

| | Detail |
|---|---|
| **Purpose** | Learn how to evaluate autonomous agent quality at scale |
| **Answer I'm looking for** | Evaluation metrics (merge rate, revert rate, CI pass rate), automated quality checks, human review rate |
| **How it helps FinSight** | When your Phase 5 agent answers financial questions, you need a way to evaluate answer quality. If the agent says "Maybank's revenue grew 15% in FY2024," you need to verify that against actual data. Agent evaluation frameworks are critical but you have none planned |
| **Which part it fixes** | [5_phase-5.md](file:///c:/Users/HP/Documents/repos/financial-insights/dev-documentation/5_phase-5.md) — no agent evaluation strategy; also informs how to evaluate the existing [jarvis_intent.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/backend/services/jarvis_intent.py) system |

### Q4.4 — Browser Navigation & UI Understanding

> *"UX-fix navigates user flows — how does the agent understand the UI? Does it use screenshots + vision models, DOM parsing, accessibility trees, or a combination? What worked best?"*

| | Detail |
|---|---|
| **Purpose** | Learn practical UI navigation techniques for AI agents |
| **Answer I'm looking for** | UI understanding approach (vision, DOM, accessibility tree), tools used (Playwright, Selenium, custom), reliability |
| **How it helps FinSight** | Your web scraper already uses Playwright to navigate 8 Malaysian company IR websites. Ling's approach to reliable UI navigation could improve scraper robustness. Also relevant if you want to build automated testing for your own frontend |
| **Which part it fixes** | [src/scraper/](file:///c:/Users/HP/Documents/repos/financial-insights/src/scraper) — Playwright-based scrapers that break when websites change layout |

---

## 5. Cross-Cutting Questions (Any Speaker)

### Q5.1 — Observability for AI Pipelines

> *"What does your AI observability stack look like in production? Do you track per-step latency, token usage, cost per inference, and model accuracy over time? What tools do you use — Langfuse, Datadog, custom dashboards?"*

| | Detail |
|---|---|
| **Purpose** | Learn production observability patterns for AI systems |
| **Answer I'm looking for** | Specific tools, key metrics tracked, alerting thresholds, dashboards |
| **How it helps FinSight** | You have Langfuse callbacks wired in but don't track meaningful business metrics. No cost-per-PDF tracking, no extraction accuracy dashboards, no alerting when extraction quality degrades |
| **Which part it fixes** | All pipeline nodes have Langfuse callbacks but track no business metrics; [5_phase-5.md](file:///c:/Users/HP/Documents/repos/financial-insights/dev-documentation/5_phase-5.md) — plans observability vaguely |

### Q5.2 — Cost Management at Scale

> *"Running AI at Deriv's scale must be expensive. How do you manage API costs — do you use caching, tiered models (cheap for easy tasks, expensive for hard ones), token budgets, or self-hosted models? What's your cost optimisation playbook?"*

| | Detail |
|---|---|
| **Purpose** | Learn cost management for production AI pipelines |
| **Answer I'm looking for** | Caching strategy (semantic cache, exact cache), model tiering, budget enforcement, self-hosting trade-offs |
| **How it helps FinSight** | You send the **full document** (often 100+ pages) to Gemini for each of 5 LLM calls. No caching, no page filtering, no token budgeting. A Maybank annual report runs ~200k tokens × 5 calls. Intelligent filtering could cut costs by 60-70% |
| **Which part it fixes** | [router.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/router.py) — sends full doc to every branch; no caching anywhere in the pipeline |

### Q5.3 — Scaling from POC to Production (The "Last Mile")

> *"The session is titled 'No Proof of Concept.' What's the hardest part of crossing from a working POC to production AI? What infrastructure, processes, or mindset shifts were needed that you didn't expect?"*

| | Detail |
|---|---|
| **Purpose** | Understand the gap between your current state and production readiness |
| **Answer I'm looking for** | Specific challenges (data quality, monitoring, edge cases, team processes), infrastructure that seems unnecessary in POC but is critical in production |
| **How it helps FinSight** | Your project has a working POC — PDFs go in, structured data comes out. But it's not production-grade: no monitoring, no retry/recovery, no human review, no CI/CD for AI, sequential processing. Understanding the "last mile" priorities helps you focus effort |
| **Which part it fixes** | Overall architecture — helps prioritise which production gaps to close first |

### Q5.4 — Human-in-the-Loop Design

> *"At Deriv, how do you design the interface between AI outputs and human reviewers? Do humans see confidence scores, explanations, or diffs? What percentage of AI outputs require human correction, and how do those corrections feed back into improving the model?"*

| | Detail |
|---|---|
| **Purpose** | Learn how to build effective human review workflows |
| **Answer I'm looking for** | Review UI design, feedback loops, correction rates, retraining pipelines |
| **How it helps FinSight** | Your pipeline has **zero human-in-the-loop**. Extracted financial data goes straight from LLM output to PostgreSQL via upsert. For a platform serving investors, this is risky. Adding a review queue with confidence-based routing would dramatically improve data quality |
| **Which part it fixes** | Missing entirely — no review exists between [merger.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/nodes/merger.py) output and [loader.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/db/loader.py) database insert |

### Q5.5 — Retry, Recovery & Handling LLM API Failures

> *"When an LLM API call fails mid-pipeline — timeout, rate limit, malformed response — how do you handle it? Per-call retry? Checkpoint and resume? And how do you ensure idempotency so retries don't produce duplicate or inconsistent data?"*

| | Detail |
|---|---|
| **Purpose** | Learn production retry/recovery patterns for LLM pipelines |
| **Answer I'm looking for** | Retry granularity, backoff strategy, checkpointing, idempotency keys |
| **How it helps FinSight** | Your LangGraph pipeline has **no retry mechanism**. If a Gemini call fails at step 3 of 5, the entire pipeline fails and Airflow retries the whole thing from scratch. Your Dify client has retries (3 attempts, linear backoff) but the LangGraph path doesn't |
| **Which part it fixes** | [graph.py](file:///c:/Users/HP/Documents/repos/financial-insights/src/pipeline/graph.py) — no per-node retry; [finsight_etl_dag.py](file:///c:/Users/HP/Documents/repos/financial-insights/dags/finsight_etl_dag.py) — retries at task level (re-processes everything) |

---

## Quick Reference: Priority Ranking

| Priority | Question | Speaker | Impact on FinSight |
|---|---|---|---|
| 🔴 Critical | Q2.1 CI/CD for AI | Daniel | Zero AI-specific CI currently |
| 🔴 Critical | Q1.2 Doer/Watcher Pattern | Waqas | No oversight on LLM-to-DB path |
| 🔴 Critical | Q3.4 Confidence Scoring | Johnathan | All extractions treated as equally reliable |
| 🔴 Critical | Q3.1 Document AI Architecture | Johnathan | Direct parallel to your PDF extraction |
| 🟠 High | Q2.2 Testing AI Systems | Daniel | Non-deterministic tests are unreliable |
| 🟠 High | Q4.1 Agent Architecture | Ling | Phase 5 blueprint |
| 🟠 High | Q4.2 Agent Safety Guardrails | Ling | MCP tools need safety design |
| 🟠 High | Q1.1 Ship-Measure-Iterate | Waqas | No measurement loop exists |
| 🟠 High | Q3.5 Ground Truth Datasets | Johnathan | Minimal ground truth data |
| 🟡 Medium | Q2.3 Versioning Prompts | Daniel | Prompts are unversioned strings |
| 🟡 Medium | Q5.1 Observability Stack | Any | Langfuse wired but under-used |
| 🟡 Medium | Q3.3 Real-Time Optimisation | Johnathan | Pipeline takes minutes per PDF |
| 🟡 Medium | Q5.2 Cost Management | Any | Full-doc sent to every LLM call |
| 🟡 Medium | Q5.5 Retry & Recovery | Any | No per-node retry in LangGraph |
| 🟢 Nice-to-have | Q5.3 POC to Production | Any | Strategic prioritisation |
| 🟢 Nice-to-have | Q2.4 Post-Mortems | Daniel | Failure pattern awareness |
| 🟢 Nice-to-have | Q4.4 Browser Navigation | Ling | Scraper robustness |
| 🟢 Nice-to-have | Q1.3 When NOT to Use AI | Waqas | Over-engineering avoidance |

---

## Conversation Starters by Speaker

> **Tip:** Frame questions around your specific project to get actionable answers. Below are openers that naturally lead into the detailed questions above.

**For Waqas:** *"I'm building a financial data extraction pipeline using LangGraph and Gemini — PDFs go in, structured JSON comes out, straight to PostgreSQL. I have no oversight layer between the AI and the database. Your Doer/Watcher pattern with Amy Sentinel seems like exactly what I need..."*

**For Daniel:** *"My CI/CD runs `python -m compileall .` — it catches syntax errors but not AI regressions. If I change a prompt tomorrow and extraction accuracy drops 20%, I wouldn't know until a user complains. How should I be testing this?"*

**For Johnathan:** *"I'm doing something similar to Xforgery but for financial reports — extracting numbers from tables in PDFs. I'm currently converting PDFs to markdown text and then using an LLM to extract structured data. Would a vision-based approach be more reliable for table extraction?"*

**For Ling:** *"I'm planning an autonomous financial analyst agent that can write SQL queries against a production database. UX-fix's approach to safely generating PRs against a real codebase seems like the same challenge — how do you prevent the agent from doing something destructive?"*
