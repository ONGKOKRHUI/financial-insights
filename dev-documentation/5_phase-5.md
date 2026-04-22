### Phase 5: Agentic Workflows, RAG Pipeline & AI Observability (Weeks 17-19) (Sem break W3-Monash W1)

**Focus:** Autonomous AI, vector/hybrid search infrastructure, Model Context Protocol (MCP), and system monitoring.

---

## What to Build

- Evolve the simple LLM calls into a multi-agent system
- Introduce an **AI chat interface** on the dashboard where users can ask complex financial questions in natural language
- Implement agent skills (via MCP) so the AI can dynamically decide whether to retrieve text from the RAG pipeline or write SQL queries against the financial data tables
- Integrate observability tools to track token usage, cost, and latency

---

## Tools & Technologies

- **LangGraph** — orchestrate agent routing and decision-making across tools
- **Langfuse** — AI observability, structured logging, token usage and cost tracking
- **Model Context Protocol (MCP)** — build secure, standardized tool-use capabilities for the agent
- **pgvector** — extend PostgreSQL to store vector embeddings of financial text, enabling semantic search (e.g., matching "revenue growth" with "increased sales figures")
- **Elasticsearch** — keyword/BM25 search for exact financial terminology (ticker symbols, dollar amounts, financial acronyms)

---

## The AI & RAG Architecture

This phase introduces **pgvector** and **Elasticsearch** because its primary objective is to build a Retrieval-Augmented Generation (RAG) pipeline to power LLM-generated financial analysis.

To generate accurate AI summaries without hallucinating, the system needs to feed the LLM highly relevant financial context. This requires advanced search capabilities:

**pgvector** — Standard PostgreSQL cannot understand the meaning of text. pgvector allows the database to store vector embeddings (mathematical representations of text). This enables *semantic search* — finding context that is conceptually similar to a query (e.g., matching "revenue growth" with "increased sales figures").

**Elasticsearch** — While vector search is great for concepts, it often struggles with exact terminology (like specific ticker symbols, exact dollar amounts, or distinct financial acronyms). Elasticsearch is used here for *keyword search* (BM25).

**Hybrid Search (RRF)** — By combining both, the system performs hybrid search using Reciprocal Rank Fusion (RRF) to merge semantic meaning (pgvector) with exact keyword hits (Elasticsearch), giving the LangChain LLM the best possible context to analyze.

This infrastructure was intentionally deferred from Phase 3 because Phase 3's goal was a clean, tested REST API for structured data retrieval — no RAG pipeline was needed for that. Phase 5 is where unstructured text (qualitative reports, footnotes, analyst commentary) gets indexed and made queryable by the AI agent.

---

## Milestone

> **A highly observable, autonomous AI assistant integrated into the platform that can reason over the financial data using a hybrid RAG pipeline.**

- IMPORTANT: Build AI Chatbots with Agentic Capabilities to call tools and use MCP. Build observability using Langfuse to track API cost. Implement pgvector + Elasticsearch hybrid search to back the RAG pipeline powering the chatbot.
