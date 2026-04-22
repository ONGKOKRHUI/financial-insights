# Brainstorming

This financial data and AI API platform is an exceptionally strong concept. It perfectly bridges the gap between a monetizable, single-sided business and a high-impact portfolio piece. It satisfies MoneyLion's requirement for rigorous data engineering and MLOps, while directly addressing Deriv's shift towards AI-first development and agentic systems.

Here is a comprehensive, 6-month Product Requirements Document (PRD) and iterative development plan designed to build this production-grade system.

### Product Overview: "FinSight API" (Working Title)

**Core Function:** An automated platform that scrapes, parses, and analyzes financial reports from Malaysian Blue-Chip companies, transforming unstructured PDFs into structured JSON and actionable intelligence.

**Monetization Strategy:** * **Free Tier:** A general website display showcasing high-level visualizations and basic company metrics.

- **Paid Tier:** Access to a detailed dashboard with deep financial analysis visualizations, an AI chatbot for custom queries, and a developer API allowing algorithmic traders to use the extracted data for model training.

---

### The 6-Month Iterative Development Plan

### Phase 1: The AI-Coded MVP & Data Acquisition (Weeks 1-3) (Monash W2-4)

**Focus:** AI-assisted development, web scraping, and foundational setup.

- **What to Build:** Create automated scripts to monitor and download quarterly and yearly financial reports (PDF format) from the websites of Malaysian Blue-Chip companies, specifically targeting Maybank, CIMB, TNB, Petronas, Maxis, Telekom, Genting, and Sunway. Setup a Next.js frontend deployed on Vercel and establish the GitHub repository to serve as an immediate portfolio showcase.
- **What to Learn & Tools to Use:** Instead of writing the scraper from scratch, use this phase to master the AI-native development workflows Deriv expects. Utilize **Claude Code**, **Cursor**, or experiment with autonomous frameworks like **OpenClaw** to generate the scraping logic. Learn **Playwright** or **Selenium** for navigating dynamic web pages to retrieve the PDFs.
- **Milestone:** A functioning automation script that successfully downloads the required PDFs, with a basic landing page live on Vercel.
- IMPORTANT: build the full frontend and backend for basic functionalities like the alphavantage page: https://www.alphavantage.co/

### Phase 2: Data Engineering & ETL Pipeline (Weeks 4-7) (Monash W5-7 + MSB)

**Focus:** Unstructured data parsing, cleaning, and database design.

- **What to Build:** Develop an automated Extract, Transform, Load (ETL) pipeline. The pipeline must ingest the downloaded PDFs, remove formatting syntax, and parse them into raw JSON while critically maintaining the structure of financial tables. Write Python scripts to clean this data, discarding noise and keeping only the relevant financial context. Append this cleaned JSON as new rows in a CSV and store it in a database.
- **What to Learn & Tools to Use:** Learn to orchestrate this workflow using **Apache Airflow** or **Prefect**. To handle complex layouts, explore advanced parsers like **Unstructured** or **PyMuPDF**. Containerize this pipeline using **Docker**.
- **Milestone:** An automated, containerized pipeline that turns raw PDFs into clean, structured data warehoused in a PostgreSQL database.
- IMPORTANT: Heavy studying and understanding of Financial reports of different companies and know which are important insights to retrieve. Use them in the post processing to get important data only. Build the full pipeline and stored in Postgres Database

### Phase 3: Backend API Hardening, Testing & Documentation (Weeks 8-11) (Monash W8-11)

**Focus:** Production-quality REST API, automated test coverage, and developer-facing documentation.

- **What to Build:** Harden the existing FastAPI backend into a production-quality API product. Add a unified `POST /search` endpoint for payload-based queries. Write a `pytest` test suite (13 tests) covering all endpoints using an in-memory SQLite fixture — no live database required. Build an interactive `/api-docs` page on the Next.js frontend with live "Try It" widgets. Update all MkDocs API reference pages with accurate content and real working examples.
- **What to Learn & Tools to Use:** Build and test with **FastAPI**, **pytest**, **httpx**, and **pytest-asyncio**. Document with **MkDocs**. Build the frontend docs page with **Next.js** and **Tailwind CSS**.
- **Milestone:** A robust FastAPI backend capable of querying precise financial metrics, with tests proving it works, and documentation explaining how to use it.
- IMPORTANT: build the RESTful API for information retrieval by the user and test that the API is working. Write the documentation on how to use the API. pgvector and Elasticsearch are **not** in scope for this phase — they are deferred to Phase 5 for the RAG/chatbot pipeline.
***builds the API product.***

### Phase 4: Full-Stack Dashboard, Auth & RBAC (Weeks 12-16) (Monash W12-Sem break W2)

**Focus:** Frontend visualizations, enterprise security, and monetization.

- **What to Build:** Connect the Next.js frontend to the FastAPI backend. Build out the interactive data visualization dashboards (graphs and charts) for financial analysis. Implement industry-level authentication, session management, and Role-Based Access Control (RBAC). This RBAC system will enforce the monetization logic, ensuring only paid users can view the detailed dashboards and visual analytics.
- **What to Learn & Tools to Use:** Learn state management using **Zustand** and **TanStack Query**. Master enterprise authentication flows using **OAuth2**, **JWT** (with HttpOnly cookies), and platforms like **Keycloak** or **Auth0**. Use libraries like **Recharts** or **Chart.js** for the visualizations.
- **Milestone:** A complete, secure web application with restricted routes and a functioning freemium model.
- IMPORTANT: now the Restful API is built, the visualisation is done calling this API. build the visualizations for paid users. build the RBAC systems with strict and production-grade security. builds the **user application that consumes that API**.

### Phase 5: Agentic Workflows, RAG Pipeline & AI Observability (Weeks 17-19) (Sem break W3-Monash W1)

**Focus:** Autonomous AI, vector/hybrid search infrastructure, Model Context Protocol (MCP), and system monitoring.

- **What to Build:** Evolve the simple LLM calls into a multi-agent system. Introduce an AI chat interface on the dashboard where users can ask complex questions in natural language. Implement agent skills (via MCP) so the AI can dynamically decide whether to retrieve text from the RAG pipeline or write SQL queries against the financial data tables. Build the hybrid search infrastructure that backs the RAG pipeline. Integrate observability tools to track token usage, cost, and latency.
- **What to Learn & Tools to Use:** Utilize **LangGraph** to orchestrate agent routing and decision-making. Implement **Langfuse** for AI observability and structured logging. Learn the **Model Context Protocol (MCP)** for secure tool-use. Introduce **pgvector** to store vector embeddings for semantic search over financial text. Integrate **Elasticsearch** for keyword/BM25 search. Combine both via **Hybrid Search (RRF)** to give the LLM the best possible retrieval context.
- **Milestone:** A highly observable, autonomous AI assistant integrated into the platform that can reason over financial data using a hybrid RAG pipeline.
- IMPORTANT: Build AI Chatbots with Agentic Capabilities to call tools and use MCP. Build observability using Langfuse to track API cost. Implement pgvector + Elasticsearch hybrid search to back the RAG pipeline powering the chatbot.

### Phase 6: Machine Learning, MLOps & Production CI/CD (Weeks 21-24) (Monash W2-5)

**Focus:** Deep learning, experiment tracking, caching, and infrastructure scaling.

- **What to Build:** Utilize the warehoused financial data to train a deep learning or machine learning model (e.g., predicting market sentiment based on the parsed reports). Implement model versioning and track training experiments. Harden the infrastructure by adding caching layers to speed up API responses, and automate the deployment process.
- **What to Learn & Tools to Use:** Train models using **PyTorch** or **XGBoost**. Implement **MLflow** for rigorous MLOps and model registry tracking. Introduce **Redis** for rate-limiting the API and caching frequent LLM queries. Build a complete CI/CD pipeline using **GitHub Actions** to automatically build Docker images and deploy the architecture to a cloud provider, leveraging existing cloud foundation knowledge to manage the infrastructure. * **Milestone:** A monetizable, production-grade system with an automated deployment pipeline and integrated machine learning models.
- IMPORTANT: Use current data to train models for prediction. implement MLOps for model versioning and fallback in production. implement strict CI/CD pipeline and testing.