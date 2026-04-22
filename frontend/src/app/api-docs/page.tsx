"use client";

import { useState, useEffect, useRef } from "react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://finsight-api.onrender.com";

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const SECTIONS = [
  { id: "introduction", label: "Introduction" },
  { id: "quickstart", label: "Quick Start" },
  { id: "authentication", label: "Authentication" },
  { id: "endpoints", label: "Endpoints" },
  { id: "errors", label: "Error Reference" },
  { id: "tryit", label: "Try It" },
];

const ENDPOINTS = [
  {
    id: "list-companies",
    method: "GET",
    path: "/companies",
    summary: "List all companies",
    description:
      "Returns a summary list of all 8 covered Malaysian Blue-Chip companies — ticker, name, sector, market cap, and currency.",
    params: [],
    curl: `curl "${BASE_URL}/companies"`,
    python: `import httpx\n\nres = httpx.get("${BASE_URL}/companies")\ncompanies = res.json()\nprint(companies[0]["ticker"])  # "MAYBANK"`,
    js: `const res = await fetch("${BASE_URL}/companies");\nconst companies = await res.json();\nconsole.log(companies[0].ticker); // "MAYBANK"`,
    response: `[\n  {\n    "ticker": "MAYBANK",\n    "name": "Malayan Banking Berhad",\n    "sector": "Financials",\n    "market_cap_bln": 102.4,\n    "currency": "MYR"\n  },\n  ...\n]`,
  },
  {
    id: "get-company",
    method: "GET",
    path: "/companies/{ticker}",
    summary: "Company detail",
    description:
      "Returns full company profile including industry, description, employee count, founding year, headquarters, and website.",
    params: [{ name: "ticker", type: "string", required: true, description: "Company ticker symbol, e.g. MAYBANK" }],
    curl: `curl "${BASE_URL}/companies/MAYBANK"`,
    python: `res = httpx.get("${BASE_URL}/companies/MAYBANK")\ndetail = res.json()\nprint(detail["industry"])  # "Banking"`,
    js: `const res = await fetch("${BASE_URL}/companies/MAYBANK");\nconst detail = await res.json();\nconsole.log(detail.industry); // "Banking"`,
    response: `{\n  "ticker": "MAYBANK",\n  "name": "Malayan Banking Berhad",\n  "sector": "Financials",\n  "industry": "Banking",\n  "description": "Maybank is Malaysia's largest bank...",\n  "market_cap_bln": 102.4,\n  "employees": 43000,\n  "founded": 1960,\n  "headquarters": "Kuala Lumpur, Malaysia",\n  "website": "https://www.maybank.com",\n  "currency": "MYR",\n  "exchange": "KLSE"\n}`,
  },
  {
    id: "kpi-summary",
    method: "GET",
    path: "/companies/{ticker}/summary",
    summary: "KPI summary",
    description:
      "Returns the latest-year KPI snapshot: revenue, net income, EPS, P/E ratio, ROE, ROACE, debt-to-equity, and dividend yield.",
    params: [{ name: "ticker", type: "string", required: true, description: "Company ticker symbol" }],
    curl: `curl "${BASE_URL}/companies/MAYBANK/summary"`,
    python: `res = httpx.get("${BASE_URL}/companies/MAYBANK/summary")\nkpi = res.json()\nprint(kpi["roe_pct"])  # 10.8`,
    js: `const res = await fetch("${BASE_URL}/companies/MAYBANK/summary");\nconst kpi = await res.json();\nconsole.log(kpi.roe_pct); // 10.8`,
    response: `{\n  "ticker": "MAYBANK",\n  "revenue_bln": 30.2,\n  "net_income_bln": 9.1,\n  "eps": 0.86,\n  "pe_ratio": 12.4,\n  "roe_pct": 10.8,\n  "roace_pct": 8.2,\n  "debt_to_equity": 0.92,\n  "dividend_yield_pct": 5.8,\n  "fiscal_year": 2024\n}`,
  },
  {
    id: "qualitative",
    method: "GET",
    path: "/companies/{ticker}/qualitative",
    summary: "Qualitative insight",
    description:
      "Returns the latest qualitative insight for a company: a future outlook paragraph and a list of key strategic events.",
    params: [{ name: "ticker", type: "string", required: true, description: "Company ticker symbol" }],
    curl: `curl "${BASE_URL}/companies/MAYBANK/qualitative"`,
    python: `res = httpx.get("${BASE_URL}/companies/MAYBANK/qualitative")\nq = res.json()\nprint(q["key_strategic_events"])`,
    js: `const res = await fetch("${BASE_URL}/companies/MAYBANK/qualitative");\nconst q = await res.json();\nconsole.log(q.key_strategic_events);`,
    response: `{\n  "ticker": "MAYBANK",\n  "fiscal_year": 2024,\n  "future_outlook": "Maybank remains well-positioned...",\n  "key_strategic_events": [\n    "Expanded ASEAN digital banking operations",\n    "Launched M25+ strategic plan"\n  ]\n}`,
  },
  {
    id: "income-statement",
    method: "GET",
    path: "/financials/{ticker}/income-statement",
    summary: "Income statement history",
    description: "Returns 5 years of annual income statement data: revenue, gross profit, operating income, net income, EPS, and margin percentages.",
    params: [{ name: "ticker", type: "string", required: true, description: "Company ticker symbol" }],
    curl: `curl "${BASE_URL}/financials/MAYBANK/income-statement"`,
    python: `res = httpx.get("${BASE_URL}/financials/MAYBANK/income-statement")\nstmt = res.json()\nfor year in stmt["data"]:\n    print(year["fiscal_year"], year["revenue_bln"])`,
    js: `const res = await fetch("${BASE_URL}/financials/MAYBANK/income-statement");\nconst stmt = await res.json();\nstmt.data.forEach(y => console.log(y.fiscal_year, y.revenue_bln));`,
    response: `{\n  "ticker": "MAYBANK",\n  "name": "Malayan Banking Berhad",\n  "currency": "MYR",\n  "data": [\n    {\n      "fiscal_year": 2020,\n      "revenue_bln": 24.1,\n      "gross_profit_bln": 18.3,\n      "operating_income_bln": 10.2,\n      "net_income_bln": 6.5,\n      "eps": 0.61,\n      "gross_margin_pct": 75.9,\n      "operating_margin_pct": 42.3,\n      "net_margin_pct": 27.0\n    },\n    ...\n  ]\n}`,
  },
  {
    id: "balance-sheet",
    method: "GET",
    path: "/financials/{ticker}/balance-sheet",
    summary: "Balance sheet history",
    description: "Returns 5 years of annual balance sheet data: total assets, liabilities, equity, cash, and total debt.",
    params: [{ name: "ticker", type: "string", required: true, description: "Company ticker symbol" }],
    curl: `curl "${BASE_URL}/financials/CIMB/balance-sheet"`,
    python: `res = httpx.get("${BASE_URL}/financials/CIMB/balance-sheet")\nbs = res.json()\nprint(bs["data"][-1]["total_equity_bln"])`,
    js: `const res = await fetch("${BASE_URL}/financials/CIMB/balance-sheet");\nconst bs = await res.json();\nconsole.log(bs.data.at(-1).total_equity_bln);`,
    response: `{\n  "ticker": "CIMB",\n  "name": "CIMB Group Holdings Berhad",\n  "currency": "MYR",\n  "data": [\n    {\n      "fiscal_year": 2024,\n      "total_assets_bln": 652.3,\n      "total_liabilities_bln": 596.1,\n      "total_equity_bln": 56.2,\n      "cash_and_equivalents_bln": 38.4,\n      "total_debt_bln": 18.7\n    }\n  ]\n}`,
  },
  {
    id: "cash-flow",
    method: "GET",
    path: "/financials/{ticker}/cash-flow",
    summary: "Cash flow history",
    description: "Returns 5 years of annual cash flow data: operating cash flow, capex, free cash flow, and dividends paid.",
    params: [{ name: "ticker", type: "string", required: true, description: "Company ticker symbol" }],
    curl: `curl "${BASE_URL}/financials/TNB/cash-flow"`,
    python: `res = httpx.get("${BASE_URL}/financials/TNB/cash-flow")\ncf = res.json()\nprint(cf["data"][-1]["free_cash_flow_bln"])`,
    js: `const res = await fetch("${BASE_URL}/financials/TNB/cash-flow");\nconst cf = await res.json();\nconsole.log(cf.data.at(-1).free_cash_flow_bln);`,
    response: `{\n  "ticker": "TNB",\n  "name": "Tenaga Nasional Berhad",\n  "currency": "MYR",\n  "data": [\n    {\n      "fiscal_year": 2024,\n      "operating_cash_flow_bln": 12.4,\n      "capital_expenditure_bln": -6.8,\n      "free_cash_flow_bln": 5.6,\n      "dividends_paid_bln": -2.1\n    }\n  ]\n}`,
  },
  {
    id: "search",
    method: "POST",
    path: "/search",
    summary: "Unified search",
    description:
      "Single payload-based endpoint. Send a ticker, statement type, and optional fiscal year — get back any financial record without memorising multiple URLs.",
    params: [
      { name: "ticker", type: "string", required: true, description: "Company ticker symbol" },
      { name: "statement_type", type: "enum", required: true, description: "income_statement | balance_sheet | cash_flow | kpi | qualitative" },
      { name: "fiscal_year", type: "integer", required: false, description: "Omit to receive the most recent year" },
    ],
    curl: `curl -X POST "${BASE_URL}/search" \\\n  -H "Content-Type: application/json" \\\n  -d '{"ticker":"MAYBANK","statement_type":"income_statement"}'`,
    python: `res = httpx.post(\n    "${BASE_URL}/search",\n    json={\n        "ticker": "MAYBANK",\n        "statement_type": "income_statement",\n        "fiscal_year": 2024,\n    },\n)\nprint(res.json()["data"]["revenue_bln"])`,
    js: `const res = await fetch("${BASE_URL}/search", {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify({\n    ticker: "MAYBANK",\n    statement_type: "income_statement",\n    fiscal_year: 2024,\n  }),\n});\nconst result = await res.json();\nconsole.log(result.data.revenue_bln);`,
    response: `{\n  "ticker": "MAYBANK",\n  "statement_type": "income_statement",\n  "fiscal_year": 2024,\n  "data": {\n    "fiscal_year": 2024,\n    "revenue_bln": 30.2,\n    "gross_profit_bln": 22.8,\n    "operating_income_bln": 12.4,\n    "net_income_bln": 9.1,\n    "eps": 0.86,\n    "gross_margin_pct": 75.5,\n    "operating_margin_pct": 41.1,\n    "net_margin_pct": 30.1\n  }\n}`,
  },
];

const ERRORS = [
  { status: "200", name: "OK", description: "Request succeeded." },
  { status: "404", name: "Not Found", description: "The requested ticker or resource does not exist.", example: '{ "detail": "Company \'XYZ\' not found." }' },
  { status: "422", name: "Unprocessable Entity", description: "Request body or path parameter failed validation (e.g. unknown statement_type).", example: '{ "detail": [{ "loc": ["body","statement_type"], "msg": "...", "type": "type_error.enum" }] }' },
  { status: "500", name: "Internal Server Error", description: "Unexpected server-side error." },
];

const TICKERS = ["MAYBANK", "CIMB", "TNB", "PETRONAS", "MAXIS", "TM", "GENTING", "SUNWAY"];
const TRY_ENDPOINTS = [
  { label: "GET /companies", url: () => `${BASE_URL}/companies`, method: "GET" },
  { label: "GET /companies/{ticker}", url: (t: string) => `${BASE_URL}/companies/${t}`, method: "GET" },
  { label: "GET /companies/{ticker}/summary", url: (t: string) => `${BASE_URL}/companies/${t}/summary`, method: "GET" },
  { label: "GET /companies/{ticker}/qualitative", url: (t: string) => `${BASE_URL}/companies/${t}/qualitative`, method: "GET" },
  { label: "GET /financials/{ticker}/income-statement", url: (t: string) => `${BASE_URL}/financials/${t}/income-statement`, method: "GET" },
  { label: "GET /financials/{ticker}/balance-sheet", url: (t: string) => `${BASE_URL}/financials/${t}/balance-sheet`, method: "GET" },
  { label: "GET /financials/{ticker}/cash-flow", url: (t: string) => `${BASE_URL}/financials/${t}/cash-flow`, method: "GET" },
  { label: "POST /search (income_statement)", url: () => `${BASE_URL}/search`, method: "POST", body: (t: string) => ({ ticker: t, statement_type: "income_statement" }) },
];

// ---------------------------------------------------------------------------
// Tiny reusable components
// ---------------------------------------------------------------------------

function MethodBadge({ method }: { method: string }) {
  const colours: Record<string, string> = {
    GET: "bg-emerald-100 text-emerald-700 border-emerald-200",
    POST: "bg-blue-100 text-blue-700 border-blue-200",
  };
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-bold uppercase ${colours[method] ?? "bg-slate-100 text-slate-700 border-slate-200"}`}>
      {method}
    </span>
  );
}

function CodeBlock({ code, language = "bash" }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <div className="relative group">
      <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-300 leading-relaxed">
        <code>{code}</code>
      </pre>
      <button
        onClick={copy}
        className="absolute right-2 top-2 rounded bg-slate-700 px-2 py-1 text-xs text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-slate-600"
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  );
}

type TabKey = "curl" | "python" | "js";
const TAB_LABELS: { key: TabKey; label: string }[] = [
  { key: "curl", label: "curl" },
  { key: "python", label: "Python" },
  { key: "js", label: "JavaScript" },
];

function CodeTabs({ endpoint }: { endpoint: (typeof ENDPOINTS)[0] }) {
  const [active, setActive] = useState<TabKey>("curl");
  const code = { curl: endpoint.curl, python: endpoint.python, js: endpoint.js }[active];
  return (
    <div>
      <div className="flex gap-1 mb-2">
        {TAB_LABELS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActive(key)}
            className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
              active === key
                ? "bg-blue-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <CodeBlock code={code} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ApiDocsPage() {
  const [activeSection, setActiveSection] = useState("introduction");
  const [tryTicker, setTryTicker] = useState("MAYBANK");
  const [tryEndpointIdx, setTryEndpointIdx] = useState(1);
  const [tryResponse, setTryResponse] = useState<string | null>(null);
  const [tryLoading, setTryLoading] = useState(false);
  const [tryError, setTryError] = useState<string | null>(null);
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  // Scroll spy
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: "-30% 0px -60% 0px" }
    );
    for (const id of SECTIONS.map((s) => s.id)) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function handleTryIt() {
    setTryLoading(true);
    setTryResponse(null);
    setTryError(null);
    const ep = TRY_ENDPOINTS[tryEndpointIdx];
    try {
      const opts: RequestInit =
        ep.method === "POST"
          ? {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(ep.body!(tryTicker)),
            }
          : { method: "GET" };
      const res = await fetch(ep.url(tryTicker), opts);
      const json = await res.json();
      setTryResponse(JSON.stringify(json, null, 2));
    } catch (err: unknown) {
      setTryError(err instanceof Error ? err.message : "Network error");
    } finally {
      setTryLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-white">
      {/* ── Sidebar ──────────────────────────────────────── */}
      <aside className="hidden lg:flex lg:flex-col sticky top-16 h-[calc(100vh-4rem)] w-60 shrink-0 overflow-y-auto border-r border-slate-800 bg-slate-900 px-4 py-8">
        <p className="mb-6 text-xs font-semibold uppercase tracking-widest text-slate-500">
          API Reference
        </p>
        <nav className="flex flex-col gap-1">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => scrollTo(s.id)}
              className={`rounded-md px-3 py-2 text-left text-sm transition-colors ${
                activeSection === s.id
                  ? "bg-blue-600 text-white font-medium"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              }`}
            >
              {s.label}
            </button>
          ))}
        </nav>

        <div className="mt-auto pt-8 border-t border-slate-800">
          <p className="text-xs text-slate-600 mb-1">Base URL</p>
          <code className="text-xs text-blue-400 break-all">
            {BASE_URL}
          </code>
          <div className="mt-3 flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-slate-500">Phase 3 — Live</span>
          </div>
        </div>
      </aside>

      {/* ── Content ──────────────────────────────────────── */}
      <main className="flex-1 min-w-0 px-6 py-12 lg:px-12 max-w-4xl">

        {/* Introduction */}
        <section id="introduction" className="mb-16 scroll-mt-20">
          <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 border border-blue-100 px-3 py-1 text-xs text-blue-600 font-medium mb-4">
            v1.0.0 · Phase 3
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 mb-4">
            FinSight REST API
          </h1>
          <p className="text-slate-600 leading-relaxed mb-4">
            The FinSight API gives developers and algorithmic traders programmatic access to
            structured financial data for 8 Malaysian Blue-Chip companies (KLSE). All data
            is returned as plain JSON — no SDK required.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
            {[
              { label: "Base URL", value: BASE_URL },
              { label: "Data coverage", value: "8 companies · 5 years" },
              { label: "Auth required", value: "None (Phase 3)" },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-medium text-slate-400 mb-1">{item.label}</p>
                <p className="text-sm font-semibold text-slate-800 break-all">{item.value}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Quick Start */}
        <section id="quickstart" className="mb-16 scroll-mt-20">
          <h2 className="text-xl font-bold text-slate-900 mb-2">Quick Start</h2>
          <p className="text-slate-500 text-sm mb-4">
            No API key needed. Hit the live API with a single command:
          </p>
          <CodeBlock code={`curl "${BASE_URL}/companies"`} />
          <p className="mt-4 text-slate-500 text-sm">
            You'll receive a JSON array of all 8 companies. To go deeper, pass a ticker
            to any of the endpoints below.
          </p>
        </section>

        {/* Authentication */}
        <section id="authentication" className="mb-16 scroll-mt-20">
          <h2 className="text-xl font-bold text-slate-900 mb-2">Authentication</h2>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 mb-4">
            <strong>Phase 3 — Open API.</strong> No authentication is required. All endpoints
            are publicly accessible.
          </div>
          <p className="text-slate-500 text-sm leading-relaxed">
            API key gating (per-user rate limits, paid tier access) is planned for Phase 4.
            When implemented, keys will be passed via an{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">X-API-Key</code>{" "}
            header. No changes to the endpoint paths or response shapes are planned.
          </p>
        </section>

        {/* Endpoints */}
        <section id="endpoints" className="mb-16 scroll-mt-20">
          <h2 className="text-xl font-bold text-slate-900 mb-6">Endpoints</h2>
          <div className="space-y-10">
            {ENDPOINTS.map((ep) => (
              <div key={ep.id} className="rounded-xl border border-slate-200 overflow-hidden">
                {/* Header */}
                <div className="flex items-center gap-3 bg-slate-50 px-5 py-4 border-b border-slate-200">
                  <MethodBadge method={ep.method} />
                  <code className="text-sm font-mono font-semibold text-slate-800">{ep.path}</code>
                  <span className="ml-auto text-xs text-slate-400">{ep.summary}</span>
                </div>

                <div className="p-5 space-y-5">
                  <p className="text-sm text-slate-600">{ep.description}</p>

                  {/* Params */}
                  {ep.params.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                        {ep.method === "POST" ? "Request Body" : "Path Parameters"}
                      </p>
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-left text-slate-400 border-b border-slate-100">
                            <th className="pb-1 font-medium">Name</th>
                            <th className="pb-1 font-medium">Type</th>
                            <th className="pb-1 font-medium">Required</th>
                            <th className="pb-1 font-medium">Description</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                          {ep.params.map((p) => (
                            <tr key={p.name}>
                              <td className="py-1.5 pr-3 font-mono text-slate-800">{p.name}</td>
                              <td className="py-1.5 pr-3 text-slate-500">{p.type}</td>
                              <td className="py-1.5 pr-3">
                                {p.required ? (
                                  <span className="text-rose-500">yes</span>
                                ) : (
                                  <span className="text-slate-400">no</span>
                                )}
                              </td>
                              <td className="py-1.5 text-slate-500">{p.description}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Code tabs */}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Example Request</p>
                    <CodeTabs endpoint={ep} />
                  </div>

                  {/* Response */}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Example Response</p>
                    <CodeBlock code={ep.response} language="json" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Error Reference */}
        <section id="errors" className="mb-16 scroll-mt-20">
          <h2 className="text-xl font-bold text-slate-900 mb-4">Error Reference</h2>
          <p className="text-sm text-slate-500 mb-5">
            Errors are returned as JSON with a{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">detail</code> field
            describing what went wrong.
          </p>
          <div className="rounded-xl border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr className="text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {ERRORS.map((e) => (
                  <tr key={e.status}>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded border px-2 py-0.5 text-xs font-bold ${
                          e.status.startsWith("2")
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : e.status.startsWith("4")
                            ? "border-amber-200 bg-amber-50 text-amber-700"
                            : "border-rose-200 bg-rose-50 text-rose-700"
                        }`}
                      >
                        {e.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-800">{e.name}</td>
                    <td className="px-4 py-3 text-slate-500">
                      {e.description}
                      {e.example && (
                        <code className="mt-1 block rounded bg-slate-50 px-2 py-1 text-xs text-slate-600 font-mono">
                          {e.example}
                        </code>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Try It */}
        <section id="tryit" className="mb-16 scroll-mt-20">
          <h2 className="text-xl font-bold text-slate-900 mb-2">Try It</h2>
          <p className="text-sm text-slate-500 mb-5">
            Fire a live request to the production API directly from your browser.
          </p>
          <div className="rounded-xl border border-slate-200 p-5 space-y-4">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1">
                <label className="block text-xs font-medium text-slate-500 mb-1">Ticker</label>
                <select
                  value={tryTicker}
                  onChange={(e) => setTryTicker(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {TICKERS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div className="flex-[2]">
                <label className="block text-xs font-medium text-slate-500 mb-1">Endpoint</label>
                <select
                  value={tryEndpointIdx}
                  onChange={(e) => setTryEndpointIdx(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {TRY_ENDPOINTS.map((ep, i) => (
                    <option key={i} value={i}>{ep.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-end">
                <button
                  onClick={handleTryIt}
                  disabled={tryLoading}
                  className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60 transition-colors"
                >
                  {tryLoading ? "Loading…" : "Send →"}
                </button>
              </div>
            </div>

            {/* URL preview */}
            <div className="rounded-lg bg-slate-900 px-4 py-2 font-mono text-xs text-slate-400">
              <span className="text-emerald-400 mr-2">{TRY_ENDPOINTS[tryEndpointIdx].method}</span>
              {TRY_ENDPOINTS[tryEndpointIdx].url(tryTicker)}
            </div>

            {/* Response */}
            {tryError && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {tryError}
              </div>
            )}
            {tryResponse && (
              <div>
                <p className="text-xs font-medium text-slate-400 mb-1">Response</p>
                <pre className="overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-300 leading-relaxed max-h-80">
                  {tryResponse}
                </pre>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
