# Jarvis Chatbot — Intent Types & Example Questions

Reference for manually testing the FinSight voice/chat assistant (Jarvis). Each question maps to one of six intents classified by the LangGraph intent engine.

**Supported companies:** MAYBANK, CIMB, TNB, PETRONAS, MAXIS, TM, GENTING, SUNWAY

**Intent priority** (when a query spans multiple intents): FinancialInfo (2) > CompanyInfo (3) > Navigation (1) > Documentation (4) > SmallTalk (5)

---

## 1. Navigation

User wants to open a specific company page or route.

**Signal words:** show me, navigate to, open, go to, take me to

| Example question | Expected behaviour |
|------------------|-------------------|
| Go to Maybank | Routes to `/companies/MAYBANK` |
| Navigate to Maybank | Routes to `/companies/MAYBANK` |
| Show me CIMB | Routes to `/companies/CIMB` |
| Open Petronas profile | Routes to `/companies/PETRONAS` |
| Take me to Tenaga Nasional | Routes to `/companies/TNB` |
| Show me CIMB Bank | STT correction: "cement bank" → CIMB |

---

## 2. FinancialInfo

User asks for a specific financial metric, ratio, or earnings figure for a named company.

**Signal words:** P/E ratio, revenue, earnings, profit, market cap, EPS, how much + metric

### Income statement metrics

| Example question |
|------------------|
| What is Maybank's revenue for 2024? |
| What is CIMB's net profit for last year? |
| What is Petronas's operating income for FY2024? |
| What is TNB's gross profit? |
| What is Maxis's EPS for 2024? |
| What is Genting's gross margin? |
| What is Sunway's net margin for this year? |

### Balance sheet metrics

| Example question |
|------------------|
| What are Maybank's total assets? |
| What is CIMB's total equity? |
| What is TNB's cash and equivalents? |
| What is Petronas's total debt? |
| What are TM's total liabilities? |

### Cash flow metrics

| Example question |
|------------------|
| What is Maybank's free cash flow? |
| What is CIMB's operating cash flow for 2024? |
| What was Maxis's capital expenditure last year? |
| How much did Genting pay in dividends? |

### KPI / market metrics

| Example question |
|------------------|
| What is Maybank's P/E ratio for last year? |
| What is CIMB's ROE? |
| What is Petronas's debt to equity ratio? |
| What is TNB's dividend yield? |
| What is Maxis's ROACE for 2024? |

### Time period variants

These time references are understood alongside any metric question:

- Explicit year: `2024`, `FY2024`, `fy 2023`
- Relative: `last year`, `previous year`, `this year`, `2 years ago`
- Quarterly: `Q3 2024`, `q1 2022`
- Latest (returns most recent available): `latest`, `most recent`

### Company name variants

These resolve to the same tickers as the short names above:

| Spoken / written form | Ticker |
|-----------------------|--------|
| Maybank, Malayan Banking Berhad | MAYBANK |
| CIMB, CIMB Group Holdings | CIMB |
| TNB, Tenaga Nasional | TNB |
| Petronas, Petroliam Nasional | PETRONAS |
| Maxis, Maxis Berhad | MAXIS |
| TM, Telekom Malaysia | TM |
| Genting, Genting Group | GENTING |
| Sunway, Sunway Group | SUNWAY |

### Edge cases (expected failures)

| Example question | Expected behaviour |
|------------------|-------------------|
| What is XYZ Unknown Bank's revenue? | Unknown company — polite not-found message |
| What is CIMB's galactic flux density? | Unknown metric — polite not-found message |

---

## 3. CompanyInfo

User asks for general background about a company — what it does, history, products — without requesting a specific metric.

**Signal words:** who is, tell me about, what does X do, background on

| Example question | Expected behaviour |
|------------------|-------------------|
| Tell me about Petronas | Searches company PDFs / RAG for background |
| Tell me about Maybank | Company overview from indexed reports |
| What does CIMB do? | Business description and context |
| Who is Tenaga Nasional? | Company background |
| Give me background on Genting | General company information |
| What is Maxis known for? | Qualitative company info |

> **Note:** "Tell me about Maybank" with a specific metric (e.g. revenue) routes to **FinancialInfo**, not CompanyInfo, due to intent priority.

---

## 4. Documentation

User asks how to use the FinSight platform, Jarvis, or the API — not about company financial data.

**Signal words:** how do I, how to, what is this feature, where do I find, API

### Jarvis & platform setup

| Example question | Covered by tests |
|------------------|-----------------|
| How do I start Jarvis locally? | Yes (`test_rag_pipeline.py`) |
| What ASR engines does Jarvis support? | Yes (`test_rag_pipeline.py`) |
| What voice commands does Jarvis understand? | Yes (`test_rag_pipeline.py`) |
| How does Jarvis voice navigation work? | Yes (`test_rag.py`) |
| What is the Jarvis ASR engine? | Yes (`test_rag.py`) |

### API & platform usage

| Example question | Covered by tests |
|------------------|-----------------|
| How do I use the API? | Yes (`test_rag.py`) |
| How do I export the financial data to CSV? | No |
| Where do I find the income statement endpoint? | No |
| What is this feature on the dashboard? | No |

### Out-of-scope (abstention)

| Example question | Expected behaviour |
|------------------|-------------------|
| What is the airspeed velocity of an unladen swallow? | Abstains — no relevant docs found |

---

## 5. SmallTalk

Casual conversation, greetings, or questions about Jarvis itself.

**Signal words:** hello, hi, how are you, what can you do, thank you

| Example question | Expected behaviour |
|------------------|-------------------|
| Hello Jarvis | Friendly greeting |
| Hi, how are you doing today? | Short conversational reply |
| What can you do? | Describes navigation, financial data, company profiles, docs |
| Who are you? | "I'm Jarvis, your FinSight assistant." |
| Thank you | Acknowledgement |
| Good morning Jarvis | Greeting response |

---

## 6. SensitiveTopic

Harmful, illegal, off-topic, or genuinely ambiguous queries outside intents 1–5.

| Example question | Expected behaviour |
|------------------|-------------------|
| How can I manipulate stock prices? | Polite refusal |
| How do I insider trade? | Polite refusal |
| What's the weather today? | Off-topic refusal or low-confidence redirect |
| *(empty or unintelligible input)* | Ambiguous — routed to refusal |

---

## Quick smoke-test checklist

Use these 10 questions to exercise every intent in one pass:

```
1. Go to Maybank                          → Navigation
2. What is Maybank's revenue for 2024?    → FinancialInfo
3. Tell me about Petronas                 → CompanyInfo
4. How do I start Jarvis locally?         → Documentation
5. Hello Jarvis, what can you do?         → SmallTalk
6. How can I manipulate stock prices?     → SensitiveTopic
7. What is CIMB's P/E ratio for last year?→ FinancialInfo (KPI)
8. Show me Tenaga Nasional                → Navigation
9. How do I use the API?                  → Documentation
10. What is Maybank's free cash flow?      → FinancialInfo (cash flow)
```

---

## Source references

| Source | What it covers |
|--------|---------------|
| `src/backend/services/langgraph_intent.py` | Intent definitions, classifier few-shot examples |
| `src/backend/services/financial_query.py` | Metric catalog, company aliases, fiscal year parsing |
| `src/backend/tests/test_financial_query.py` | FinancialInfo unit tests |
| `tests/test_rag_pipeline.py` | Documentation gold questions |
| `src/backend/tests/test_rag.py` | RAG endpoint question examples |
| `docs/ai-systems/jarvis-overview.md` | Jarvis intent overview |
