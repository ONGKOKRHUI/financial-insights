"""Jarvis intent pipeline implemented with LangChain + LangGraph.

Mirrors the Dify workflow node-by-node:
  START → refine_transcript → classify_intent → [conditional router]
            ├── intent_id=1 → handle_navigation
            ├── intent_id=2 → handle_financial
            ├── intent_id=3 → handle_company_info
            ├── intent_id=4 → handle_documentation
            ├── intent_id=5 → handle_small_talk
            └── default     → handle_sensitive

Public API:
    run_jarvis_graph(raw_transcript, session_id) -> dict
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

# ── Models ────────────────────────────────────────────────────────────────────

#
# Use the Jarvis-specific model if set (keeps intent engine consistent with
# whichever Gemini model your ASR setup already supports).
#
_FLASH_MODEL = os.getenv("JARVIS_GEMINI_MODEL") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")


def _get_llm(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=_FLASH_MODEL,
        temperature=temperature,
        google_api_key=_GOOGLE_API_KEY,
    )


# ── Pydantic schema for structured intent output ──────────────────────────────

class IntentEntities(BaseModel):
    company: Optional[str] = Field(None, description="Company name in UPPERCASE e.g. MAYBANK, CIMB, PETRONAS — or null")
    metric: Optional[str] = Field(None, description="Financial metric e.g. P/E ratio, revenue, EPS — or null")
    time_period: Optional[str] = Field(None, description="Time reference e.g. Q3 2024, last year, FY2023 — or null")
    navigation_target: Optional[str] = Field(None, description="Inferred Next.js route e.g. /companies/MAYBANK — or null")


class IntentOutput(BaseModel):
    refined_text: str = Field(..., description="The query as understood after any final STT corrections")
    intent_id: int = Field(..., description="Integer 1-6", ge=1, le=6)
    intent_name: str = Field(..., description="Navigation|FinancialInfo|CompanyInfo|Documentation|SmallTalk|SensitiveTopic")
    confidence: float = Field(..., description="Float 0.0-1.0", ge=0.0, le=1.0)
    entities: IntentEntities = Field(default_factory=IntentEntities)
    reasoning: str = Field(..., description="One sentence explaining the classification decision")


# ── LangGraph State ───────────────────────────────────────────────────────────

class JarvisState(TypedDict):
    raw_transcript: str
    session_id: str
    refined_text: str
    intent_id: int
    intent_name: str
    confidence: float
    entities: dict
    reasoning: str
    output: dict


# ── System prompts ────────────────────────────────────────────────────────────

_REFINEMENT_SYSTEM_PROMPT = """\
You are a speech-to-text correction engine for a Malaysian financial platform called FinSight.

Role: Preprocessing step before intent classification.
Goal: Fix transcription errors without changing the user's meaning.

Correction rules (in order of priority):

1. PREPOSITIONS: Fix missing/wrong prepositions
   - "navigate the Maybank" → "navigate to Maybank"
   - "show me of the CIMB" → "show me CIMB"

2. COMPANY NAMES: Correct phonetic mismatches common in Malaysian-accented English
   - "cement bank" → "CIMB Bank"
   - "hong lion" → "Hong Leong"
   - "tea and bee" → "TNB" (Tenaga Nasional)
   - "petronus" → "Petronas"
   - "may ban" or "may bank" → "Maybank"

3. FINANCIAL TERMS: Restore standard abbreviations
   - "pee ee ratio" → "P/E ratio"
   - "eps" → "EPS"
   - "ebitda" → "EBITDA"

4. GRAMMAR: Correct only STT-caused grammar errors, not stylistic choices

5. NO CHANGE RULE: If the transcript is already intelligible, return it exactly as received.

Output: Return ONLY the corrected sentence. No explanation, no JSON, no quotes.\
"""

_CLASSIFIER_SYSTEM_PROMPT = """\
### Role
You are Jarvis, an AI intent classification engine for FinSight — a Malaysian financial data platform.
Your sole purpose is to analyze a voice-transcribed user query and output a structured JSON object identifying the user's intent and extracting key entities.

### Intent Definitions

| ID | Name | When to use | Signal words |
|----|------|-------------|--------------|
| 1 | Navigation | User wants to open a specific page or company profile | "show me", "navigate to", "open", "go to", "take me to" |
| 2 | FinancialInfo | Asking about specific financial metrics, ratios, stock prices, earnings | "P/E ratio", "revenue", "earnings", "profit", "market cap", "EPS", "how much" + metric |
| 3 | CompanyInfo | General background about a company — what it does, history, products | "who is", "tell me about", "what does X do", "background on" |
| 4 | Documentation | Questions about how to use the FinSight platform itself | "how do I", "how to", "what is this feature", "where do I find", "API" |
| 5 | SmallTalk | Casual conversation, greetings, questions about Jarvis itself | "hello", "hi", "how are you", "what can you do", "thank you" |
| 6 | SensitiveTopic | Harmful, illegal, off-topic, or genuinely ambiguous queries | Anything outside intents 1–5 |

### Instructions
1. Read the refined transcript carefully.
2. Determine the PRIMARY intent from the 6 categories. If the query spans multiple intents, apply this priority: 2 > 3 > 1 > 4 > 5.
3. Extract all relevant entities.
4. If confidence is below 0.6 or the topic is harmful or completely unrelated to finance/FinSight, return intent_id=6.

### Few-Shot Examples

Input: "navigate the Maybank"
refined_text: "navigate to Maybank", intent_id: 1, intent_name: "Navigation", confidence: 0.97, entities: {company: "MAYBANK", navigation_target: "/companies/MAYBANK"}, reasoning: "'Navigate' + company name is a clear navigation intent."

Input: "what is Maybank's PE ratio for last year"
refined_text: "What is Maybank's P/E ratio for last year?", intent_id: 2, intent_name: "FinancialInfo", confidence: 0.99, entities: {company: "MAYBANK", metric: "P/E ratio", time_period: "last year"}, reasoning: "Specific financial metric P/E ratio requested for a named company with a time period."

Input: "hello jarvis how are you doing today"
refined_text: "Hello Jarvis, how are you doing today?", intent_id: 5, intent_name: "SmallTalk", confidence: 0.98, entities: {}, reasoning: "Greeting with no financial or navigation intent."

Input: "how can I manipulate stock prices"
refined_text: "How can I manipulate stock prices?", intent_id: 6, intent_name: "SensitiveTopic", confidence: 0.99, entities: {}, reasoning: "Query involves illegal financial activity."\
"""

_SMALL_TALK_SYSTEM_PROMPT = """\
You are Jarvis, the friendly and witty AI assistant for FinSight — a Malaysian financial data platform.

Personality:
- Warm, professional, and slightly playful (think: smart colleague, not a robot)
- Keep responses short — 1 to 3 sentences maximum
- You can mention your capabilities: navigation, financial data, company profiles, documentation
- Do NOT answer questions about sensitive topics or give financial advice
- If asked your name: "I'm Jarvis, your FinSight assistant."\
"""

# ── Route map (mirrors Nav Route Builder Code node) ───────────────────────────

_ROUTE_MAP: dict[str, str] = {
    "MAYBANK":      "/companies/MAYBANK",
    "CIMB":         "/companies/CIMB",
    "PUBLIC BANK":  "/companies/PUBLIC-BANK",
    "RHB":          "/companies/RHB",
    "HONG LEONG":   "/companies/HONG-LEONG",
    "PETRONAS":     "/companies/PETRONAS",
    "TENAGA":       "/companies/TNB",
    "TNB":          "/companies/TNB",
    "SUNWAY":       "/companies/SUNWAY",
    "AXIATA":       "/companies/AXIATA",
    "MAXIS":        "/companies/MAXIS",
    "DIGI":         "/companies/DIGI",
    "TM":           "/companies/TM",
    "GENTING":      "/companies/GENTING",
}


# ── Graph nodes ───────────────────────────────────────────────────────────────

def refine_transcript(state: JarvisState) -> dict:
    """Fix STT errors in the raw transcript (Transcript Refinement LLM node)."""
    llm = _get_llm(temperature=0.1)
    messages = [
        SystemMessage(content=_REFINEMENT_SYSTEM_PROMPT),
        HumanMessage(content=state["raw_transcript"]),
    ]
    result = llm.invoke(messages)
    refined = result.content.strip()
    logger.debug("refine_transcript: %r → %r", state["raw_transcript"], refined)
    return {"refined_text": refined}


def classify_intent(state: JarvisState) -> dict:
    """Classify intent and extract entities (Intent Classifier + JSON Parser nodes)."""
    llm = _get_llm(temperature=0.0).with_structured_output(IntentOutput)
    messages = [
        SystemMessage(content=_CLASSIFIER_SYSTEM_PROMPT),
        HumanMessage(content=f"Transcript to classify: {state['refined_text']}"),
    ]
    result: IntentOutput = llm.invoke(messages)

    # Clamp intent_id to valid range
    intent_id = max(1, min(6, int(result.intent_id)))

    logger.debug(
        "classify_intent: intent_id=%d (%s) confidence=%.2f",
        intent_id, result.intent_name, result.confidence,
    )

    return {
        "refined_text": result.refined_text,
        "intent_id": intent_id,
        "intent_name": result.intent_name,
        "confidence": result.confidence,
        "entities": result.entities.model_dump(),
        "reasoning": result.reasoning,
    }


def _route_by_intent(state: JarvisState) -> str:
    """Conditional edge: route to handler node based on intent_id."""
    mapping = {
        1: "handle_navigation",
        2: "handle_financial",
        3: "handle_company_info",
        4: "handle_documentation",
        5: "handle_small_talk",
    }
    return mapping.get(state.get("intent_id", 6), "handle_sensitive")


def handle_navigation(state: JarvisState) -> dict:
    """Map company entity to a Next.js route (Nav Route Builder Code node)."""
    company = (state["entities"].get("company") or "").strip().upper()
    navigation_target = state["entities"].get("navigation_target") or ""

    target = _ROUTE_MAP.get(company)
    if not target and navigation_target:
        target = navigation_target
    if not target and company:
        target = f"/companies/{company.replace(' ', '-')}"
    if not target:
        target = "/companies"

    display_name = company.title() if company else "the requested page"
    voice_message = f"Navigating to {display_name}."

    output = {
        "action": "navigate",
        "target": target,
        "message": voice_message,
        "voice": voice_message,
        "intent_id": 1,
        "refined_transcript": state["refined_text"],
        "sources": [],
        "confidence": 1.0,
        "engine": "langgraph",
    }
    return {"output": output}


def handle_financial(state: JarvisState) -> dict:
    """Retrieve a financial metric from PostgreSQL (Intent 2 — FinancialInfo).

    Entity resolution, metric catalog lookup, fiscal-year parsing, and database
    query are all delegated to financial_query.query_financial_intent so that
    this node stays a thin orchestration wrapper.
    """
    from services.financial_query import query_financial_intent

    company = state["entities"].get("company") or ""
    metric_text = state["entities"].get("metric") or ""
    time_period = state["entities"].get("time_period") or None

    result = query_financial_intent(
        company=company or None,
        metric_text=metric_text or None,
        time_period=time_period,
    )

    output = {
        "action": "respond",
        "target": None,
        "message": result["message"],
        "voice": result["voice"],
        "intent_id": 2,
        "refined_transcript": state["refined_text"],
        "sources": result["sources"],
        "confidence": state["confidence"],
        "engine": "langgraph",
    }
    return {"output": output}


def _call_rag(
    question: str,
    scope: str,
    ticker: Optional[str] = None,
    top_k: int = 4,
) -> tuple[str, str, list[dict]]:
    """Call the RAG retrieval + answer service.

    Returns (answer_text, confidence, sources_list).
    Falls back gracefully on any error.
    """
    try:
        from services.rag_retriever import retrieve
        from services.rag_answer import generate_answer

        result = retrieve(question=question, scope=scope, ticker=ticker, top_k=top_k)
        answer_text, _abstained, confidence = generate_answer(
            question=question, chunks=result.chunks
        )
        sources = [
            {
                "title": c.title,
                "source_path": c.source_path,
                "snippet": c.snippet,
                "rank": c.rank,
            }
            for c in result.chunks[:3]
        ]
        return answer_text, confidence, sources
    except Exception as exc:
        logger.warning("RAG service call failed: %s", exc)
        return "", "low", []


# ── Company profile — direct PostgreSQL lookup ────────────────────────────────


def _get_company_profile(ticker: str) -> tuple[str, list[dict]]:
    """Fetch company data from PostgreSQL and return (formatted_text, sources).

    Queries Company, KPISummary, and QualitativeInsight models directly so that
    handle_company_info never depends on an Elasticsearch index that contains no
    company documents.
    """
    import json as _json

    try:
        from database import SessionLocal
        from models import (
            Company,
            KPISummary as KPISummaryModel,
            QualitativeInsight as QualitativeInsightModel,
        )

        db = SessionLocal()
        try:
            company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
            if not company:
                return "", []

            kpi = (
                db.query(KPISummaryModel)
                .filter(KPISummaryModel.ticker == ticker.upper())
                .order_by(KPISummaryModel.fiscal_year.desc())
                .first()
            )
            qualitative = (
                db.query(QualitativeInsightModel)
                .filter(QualitativeInsightModel.ticker == ticker.upper())
                .order_by(QualitativeInsightModel.fiscal_year.desc())
                .first()
            )
        finally:
            db.close()

        lines: list[str] = [
            f"## {company.name} ({company.ticker})",
            f"Sector: {company.sector} | Industry: {company.industry}",
        ]
        if company.founded:
            lines.append(f"Founded: {company.founded}")
        if company.headquarters:
            lines.append(f"Headquarters: {company.headquarters}")
        if company.employees:
            lines.append(f"Employees: {company.employees:,}")
        if company.market_cap_bln:
            lines.append(f"Market Cap: MYR {company.market_cap_bln:.1f}B")
        if company.description:
            lines.append(f"\n{company.description}")

        if kpi:
            lines.append(f"\n### Key Financials (FY{kpi.fiscal_year})")
            if kpi.revenue_bln is not None:
                lines.append(f"- Revenue: MYR {kpi.revenue_bln:.1f}B")
            if kpi.net_income_bln is not None:
                lines.append(f"- Net Income: MYR {kpi.net_income_bln:.1f}B")
            if kpi.eps is not None:
                lines.append(f"- EPS: {kpi.eps}")
            if kpi.pe_ratio is not None:
                lines.append(f"- P/E Ratio: {kpi.pe_ratio}")
            if kpi.roe_pct is not None:
                lines.append(f"- ROE: {kpi.roe_pct}%")
            if kpi.dividend_yield_pct is not None:
                lines.append(f"- Dividend Yield: {kpi.dividend_yield_pct}%")

        if qualitative:
            lines.append(f"\n### Outlook (FY{qualitative.fiscal_year})")
            if qualitative.future_outlook:
                lines.append(qualitative.future_outlook)
            if qualitative.key_strategic_events:
                try:
                    events = _json.loads(qualitative.key_strategic_events)
                    if events:
                        lines.append("\nKey Strategic Events:")
                        for e in events[:3]:
                            lines.append(f"- {e}")
                except Exception:
                    pass

        context_text = "\n".join(lines)
        sources = [
            {
                "title": f"{company.name} ({company.ticker}) — Company Profile",
                "source_path": f"/companies/{company.ticker}",
                "snippet": (company.description or "")[:200],
                "rank": 1,
            }
        ]
        return context_text, sources

    except Exception as exc:
        logger.warning("Company DB lookup failed for %s: %s", ticker, exc)
        return "", []


# ── Documentation — file-based fallback ──────────────────────────────────────


def _load_docs_context() -> str:
    """Read docs/api-reference/*.md and frontend/src/app/api-docs/page.tsx.

    Used as a fallback when the Elasticsearch index has no indexed documentation.
    """
    from pathlib import Path

    file_path = Path(__file__).resolve()
    repo_root = None

    # Resolve repo root robustly across local dev and Docker.
    for parent in file_path.parents:
        if (parent / "docs" / "api-reference").exists():
            repo_root = parent
            break
    if repo_root is None:
        if (Path("/app") / "docs" / "api-reference").exists():
            repo_root = Path("/app")
        else:
            repo_root = Path.cwd()

    parts: list[str] = []

    docs_dir = repo_root / "docs" / "api-reference"
    if docs_dir.exists():
        for md_file in sorted(docs_dir.rglob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                title = md_file.stem.replace("-", " ").title()
                parts.append(f"## {title}\n\n{content[:3000]}")
            except Exception as exc:
                logger.debug("Could not read %s: %s", md_file, exc)
    else:
        logger.debug("docs/api-reference/ not found at %s", docs_dir)

    # Also include endpoint summaries extracted from page.tsx
    tsx_path = repo_root / "frontend" / "src" / "app" / "api-docs" / "page.tsx"
    if tsx_path.exists():
        try:
            tsx_text = tsx_path.read_text(encoding="utf-8")
            extracted = _extract_tsx_docs(tsx_text)
            if extracted:
                parts.append(f"## API Docs Page (page.tsx)\n\n{extracted}")
        except Exception as exc:
            logger.debug("Could not read page.tsx: %s", exc)

    return "\n\n---\n\n".join(parts)


def _extract_tsx_docs(text: str) -> str:
    """Extract endpoint documentation strings from api-docs/page.tsx.

    Pulls method, path, summary, description, and param descriptions from the
    ENDPOINTS constant so the content is indexable / usable as LLM context.
    """
    import re

    sections: list[str] = []

    # Authentication note (hardcoded — present in the JSX section)
    sections.append(
        "## Authentication\n"
        "Phase 3 — Open API. No authentication is required. All endpoints are publicly accessible.\n"
        "API keys (X-API-Key header) are planned for Phase 4 — no endpoint path changes expected."
    )

    # ENDPOINTS array: extract method, path, summary, description
    # Each entry looks like:
    #   id: "...",
    #   method: "GET",
    #   path: "/companies",
    #   summary: "...",
    #   description: "..." or description:\n      "..."
    ep_re = re.compile(
        r'id:\s*"([^"]+)",\s*\n\s*method:\s*"(GET|POST)",\s*\n\s*path:\s*"([^"]+)",\s*\n'
        r'\s*summary:\s*"([^"]+)",\s*\n\s*description:\s*\n?\s*"((?:[^"\\]|\\.)*)"',
        re.DOTALL,
    )
    param_re = re.compile(
        r'name:\s*"([^"]+)",\s*type:\s*"([^"]+)",\s*required:\s*(true|false),\s*description:\s*"([^"]+)"'
    )

    for m in ep_re.finditer(text):
        _id, method, path, summary, description = m.groups()
        section_lines = [
            f"### {method} {path}",
            f"**{summary}**",
            "",
            description.strip(),
        ]

        # Find the params array for this endpoint (search a window after the description)
        start = m.end()
        window = text[start : start + 600]
        params = param_re.findall(window)
        if params:
            section_lines.append("\nParameters:")
            for pname, ptype, preq, pdesc in params:
                req_label = "required" if preq == "true" else "optional"
                section_lines.append(f"- `{pname}` ({ptype}, {req_label}): {pdesc}")

        sections.append("\n".join(section_lines))

    # ERRORS array
    error_re = re.compile(
        r'status:\s*"(\d+)",\s*name:\s*"([^"]+)",\s*description:\s*"([^"]+)"'
    )
    error_lines = ["## HTTP Error Codes"]
    for em in error_re.finditer(text):
        status, name, desc = em.groups()
        error_lines.append(f"- **{status} {name}**: {desc}")
    if len(error_lines) > 1:
        sections.append("\n".join(error_lines))

    return "\n\n".join(sections)


def _answer_from_context(question: str, context: str) -> str:
    """Generate a grounded answer from inline file context using Gemini.

    Used when the Elasticsearch index is empty or returns no relevant chunks.
    Returns an empty string if the context does not contain a useful answer.
    """
    if not context.strip():
        return ""

    system = (
        "You are a precise documentation assistant for FinSight, a Malaysian financial data platform. "
        "Answer the user's question using ONLY the context provided below. "
        "Be concise (2–5 sentences). "
        "If the context does not contain enough information, reply with exactly: "
        "ABSTAIN: Not found in the documentation."
    )
    user = f"Context:\n\n{context}\n\nQuestion: {question}\n\nAnswer:"

    try:
        result = _get_llm(temperature=0.1).invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        answer = result.content.strip()
        if answer.startswith("ABSTAIN:"):
            return ""
        return answer
    except Exception as exc:
        logger.warning("_answer_from_context LLM call failed: %s", exc)
        return ""


def handle_company_info(state: JarvisState) -> dict:
    """Retrieve company profile from PostgreSQL (direct DB query, not ES)."""
    company = state["entities"].get("company") or ""
    ticker = (state["entities"].get("company") or "").strip().upper() or None
    question = state["refined_text"] or f"Tell me about {company}"

    context_text, sources = "", []
    if ticker:
        context_text, sources = _get_company_profile(ticker)

    if not context_text:
        message = (
            f"I couldn't find profile information for {company}. "
            "Try navigating to their company page instead."
        ) if company else "Please specify a company name."
        output = {
            "action": "respond",
            "target": None,
            "message": message,
            "voice": message,
            "intent_id": 3,
            "refined_transcript": state["refined_text"],
            "sources": [],
            "confidence": state["confidence"],
            "engine": "langgraph",
        }
        return {"output": output}

    answer = _answer_from_context(question, context_text) or context_text
    voice = answer[:300] if len(answer) > 300 else answer

    output = {
        "action": "respond",
        "target": None,
        "message": answer,
        "voice": voice,
        "intent_id": 3,
        "refined_transcript": state["refined_text"],
        "sources": sources,
        "confidence": state["confidence"],
        "engine": "langgraph",
    }
    return {"output": output}


def handle_documentation(state: JarvisState) -> dict:
    """Answer platform/API documentation questions.

    Primary path: Elasticsearch hybrid RAG (BM25 + KNN) over indexed docs.
    Fallback path: read docs/api-reference/*.md + page.tsx directly and answer
    with Gemini — used when the ES index is empty or returns no relevant chunks.
    """
    question = state["refined_text"]

    # 1. Try ES-based hybrid retrieval first
    answer, _confidence, sources = _call_rag(
        question=question,
        scope="documentation",
        top_k=4,
    )

    # 2. Fall back to direct file reading when ES returns nothing
    if not sources:
        logger.info("ES returned no doc chunks — falling back to file-based context")
        context = _load_docs_context()
        answer = _answer_from_context(question, context)
        if answer:
            sources = [
                {
                    "title": "FinSight API Reference",
                    "source_path": "docs/api-reference/",
                    "snippet": "",
                    "rank": 1,
                }
            ]

    if not answer:
        message = (
            "I couldn't find a relevant answer in the FinSight documentation. "
            "You can browse the full API reference at /api-docs."
        )
        voice = "I couldn't find documentation for that. Try browsing the API docs page."
    else:
        message = answer
        voice = answer[:300] if len(answer) > 300 else answer

    output = {
        "action": "respond",
        "target": None,
        "message": message,
        "voice": voice,
        "intent_id": 4,
        "refined_transcript": state["refined_text"],
        "sources": sources,
        "confidence": state["confidence"],
        "engine": "langgraph",
    }
    return {"output": output}


def handle_small_talk(state: JarvisState) -> dict:
    """Generate a conversational reply (Small Talk LLM + Formatter nodes)."""
    llm = _get_llm(temperature=0.7)
    messages = [
        SystemMessage(content=_SMALL_TALK_SYSTEM_PROMPT),
        HumanMessage(content=state["refined_text"]),
    ]
    result = llm.invoke(messages)
    reply = result.content.strip()

    output = {
        "action": "respond",
        "target": None,
        "message": reply,
        "voice": reply,
        "intent_id": 5,
        "refined_transcript": state["refined_text"],
        "sources": [],
        "confidence": state["confidence"],
        "engine": "langgraph",
    }
    return {"output": output}


def handle_sensitive(state: JarvisState) -> dict:
    """Hard-coded refusal for sensitive or unrecognised topics (Refusal Template node)."""
    output = {
        "action": "respond",
        "target": None,
        "message": (
            "I'm not able to assist with that topic. "
            "I can help you navigate the platform, look up financial data, "
            "or answer questions about FinSight."
        ),
        "voice": "I cannot assist with that. I can help you navigate FinSight or look up financial information.",
        "intent_id": 6,
        "refined_transcript": state.get("refined_text", state.get("raw_transcript", "")),
        "sources": [],
        "confidence": 1.0,
        "engine": "langgraph",
    }
    return {"output": output}


# ── Build graph ───────────────────────────────────────────────────────────────

def _build_graph():
    builder = StateGraph(JarvisState)

    builder.add_node("refine_transcript", refine_transcript)
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("handle_navigation", handle_navigation)
    builder.add_node("handle_financial", handle_financial)
    builder.add_node("handle_company_info", handle_company_info)
    builder.add_node("handle_documentation", handle_documentation)
    builder.add_node("handle_small_talk", handle_small_talk)
    builder.add_node("handle_sensitive", handle_sensitive)

    builder.add_edge(START, "refine_transcript")
    builder.add_edge("refine_transcript", "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        _route_by_intent,
        {
            "handle_navigation": "handle_navigation",
            "handle_financial": "handle_financial",
            "handle_company_info": "handle_company_info",
            "handle_documentation": "handle_documentation",
            "handle_small_talk": "handle_small_talk",
            "handle_sensitive": "handle_sensitive",
        },
    )
    for handler in (
        "handle_navigation",
        "handle_financial",
        "handle_company_info",
        "handle_documentation",
        "handle_small_talk",
        "handle_sensitive",
    ):
        builder.add_edge(handler, END)

    return builder.compile()


_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ── Public API ────────────────────────────────────────────────────────────────

def run_jarvis_graph(raw_transcript: str, session_id: str = "anonymous") -> dict:
    """Run the full Jarvis intent pipeline via LangGraph.

    Args:
        raw_transcript: Raw text from the ASR engine (may contain STT errors).
        session_id: Optional session identifier (reserved for future memory).

    Returns:
        Unified output dict:
            {
                "action": "navigate" | "respond",
                "target": str | None,
                "message": str,
                "voice": str,
                "intent_id": int,
                "refined_transcript": str,
                "sources": list,
                "confidence": float,
                "engine": "langgraph",
            }

    Raises:
        Exception: Propagated to caller; caller should fall back to keyword engine.
    """
    graph = _get_graph()
    initial_state: JarvisState = {
        "raw_transcript": raw_transcript,
        "session_id": session_id,
        "refined_text": "",
        "intent_id": 6,
        "intent_name": "SensitiveTopic",
        "confidence": 0.0,
        "entities": {},
        "reasoning": "",
        "output": {},
    }
    final_state = graph.invoke(initial_state)
    return final_state["output"]
