import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "FinSight — Malaysian Financial Data API",
  description:
    "Enterprise-grade financial data API for Malaysian Blue-Chip companies. Structured income statements, KPIs, and historical trend data via a developer-friendly REST API.",
};

const FEATURES = [
  {
    icon: "📊",
    title: "Structured Financial Data",
    description:
      "Access 5-year historical income statements, balance sheets, and cash flow data for 8 Malaysian Blue-Chip companies in clean JSON format.",
  },
  {
    icon: "⚡",
    title: "Fast REST API",
    description:
      "Developer-friendly endpoints built with FastAPI. Retrieve company KPIs, income statements, and metadata with a single HTTP request.",
  },
  {
    icon: "📈",
    title: "Visual Analytics",
    description:
      "Interactive revenue trend charts, profitability margin analysis, and income breakdowns built with Recharts for instant insights.",
  },
  {
    icon: "🏦",
    title: "KLSE Blue-Chips",
    description:
      "Covers Malaysia's most influential listed companies: Maybank, CIMB, TNB, Petronas, Maxis, TM, Genting, and Sunway.",
  },
];

const COMPANIES = [
  { ticker: "MAYBANK", name: "Malayan Banking", sector: "Financials" },
  { ticker: "CIMB", name: "CIMB Group", sector: "Financials" },
  { ticker: "TNB", name: "Tenaga Nasional", sector: "Utilities" },
  { ticker: "PETRONAS", name: "Petroliam Nasional", sector: "Energy" },
  { ticker: "MAXIS", name: "Maxis Berhad", sector: "Telecom" },
  { ticker: "TM", name: "Telekom Malaysia", sector: "Telecom" },
  { ticker: "GENTING", name: "Genting Berhad", sector: "Consumer" },
  { ticker: "SUNWAY", name: "Sunway Berhad", sector: "Real Estate" },
];

const API_EXAMPLES = [
  { method: "GET", path: "/companies", description: "List all companies" },
  { method: "GET", path: "/companies/{ticker}", description: "Company detail" },
  { method: "GET", path: "/companies/{ticker}/summary", description: "KPI summary" },
  { method: "GET", path: "/financials/{ticker}/income-statement", description: "5-year income statement" },
];

export default function HomePage() {
  return (
    <div>
      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 py-24 text-white">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCA1MCBMIDQ1IDUwIiBmaWxsPSJub25lIiBzdHJva2U9InJnYmEoMjU1LDI1NSwyNTUsMC4wMykiIHN0cm9rZS13aWR0aD0iMSIvPjwvcGF0dGVybj48L2RlZnM+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsbD0idXJsKCNncmlkKSIvPjwvc3ZnPg==')] opacity-40" />
        <div className="relative mx-auto max-w-7xl px-4 text-center sm:px-6 lg:px-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-400/30 bg-blue-500/10 px-4 py-1.5 text-xs font-medium text-blue-300 mb-6">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
            Phase 3 — API Now Live
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl">
            Financial Data API for
            <span className="block text-blue-400 mt-1">Malaysian Blue-Chips</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-300">
            Structured income statements, KPI summaries, and historical trend data
            for KLSE-listed companies — delivered through a developer-friendly REST API.
          </p>
          <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <Link
              href="/companies"
              className="rounded-lg bg-blue-600 px-8 py-3 text-sm font-semibold text-white hover:bg-blue-500 transition-colors shadow-lg shadow-blue-500/25"
            >
              Explore Companies →
            </Link>
            <Link
              href="/api-docs"
              className="rounded-lg border border-white/20 bg-white/5 px-8 py-3 text-sm font-semibold text-white hover:bg-white/10 transition-colors"
            >
              View API Docs →
            </Link>
            <Link
              href="/companies/MAYBANK"
              className="rounded-lg border border-white/10 bg-white/5 px-8 py-3 text-sm font-semibold text-slate-300 hover:bg-white/10 transition-colors"
            >
              Demo: MAYBANK
            </Link>
          </div>
        </div>
      </section>

      {/* ── Company Quick Links ───────────────────────────── */}
      <section className="border-b border-slate-200 bg-white py-6">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 mr-2">
              Available:
            </span>
            {COMPANIES.map((c) => (
              <Link
                key={c.ticker}
                href={`/companies/${c.ticker}`}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600 transition-all"
              >
                {c.ticker}
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────── */}
      <section className="py-20 bg-slate-50">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-slate-900">
              Everything you need for financial analysis
            </h2>
            <p className="mt-3 text-slate-500 max-w-xl mx-auto">
              From raw data to interactive visualizations — all in one platform.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((feature) => (
              <div
                key={feature.title}
                className="rounded-xl border border-slate-200 bg-white p-6 hover:shadow-md transition-shadow"
              >
                <div className="text-3xl mb-3">{feature.icon}</div>
                <h3 className="text-sm font-semibold text-slate-900">
                  {feature.title}
                </h3>
                <p className="mt-2 text-sm text-slate-500 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── API Preview ───────────────────────────────────── */}
      <section className="py-20 bg-white">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-2 items-center">
            <div>
              <h2 className="text-3xl font-bold text-slate-900">
                Simple, intuitive API
              </h2>
              <p className="mt-4 text-slate-500 leading-relaxed">
                Four clean endpoints give you everything from company metadata to
                5-year income statement history. No complex authentication — just
                straightforward REST.
              </p>
              <div className="mt-6 space-y-3">
                {API_EXAMPLES.map((ex) => (
                  <div
                    key={ex.path}
                    className="flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50 px-4 py-3"
                  >
                    <span className="text-xs font-bold text-blue-600 bg-blue-50 border border-blue-100 rounded px-1.5 py-0.5">
                      {ex.method}
                    </span>
                    <code className="text-xs text-slate-700 font-mono flex-1">
                      {ex.path}
                    </code>
                    <span className="text-xs text-slate-400">{ex.description}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl bg-slate-900 p-5 font-mono text-xs text-slate-300 leading-relaxed overflow-hidden">
              <div className="flex items-center gap-1.5 mb-4">
                <div className="h-2.5 w-2.5 rounded-full bg-red-400" />
                <div className="h-2.5 w-2.5 rounded-full bg-yellow-400" />
                <div className="h-2.5 w-2.5 rounded-full bg-green-400" />
                <span className="ml-2 text-slate-500 text-xs">GET /companies/MAYBANK/summary</span>
              </div>
              <pre className="whitespace-pre-wrap">{`{
  "ticker": "MAYBANK",
  "revenue_bln": 30.2,
  "net_income_bln": 9.1,
  "eps": 0.86,
  "pe_ratio": 12.4,
  "roe_pct": 10.8,
  "debt_to_equity": 0.92,
  "dividend_yield_pct": 5.8,
  "fiscal_year": 2024
}`}</pre>
            </div>
          </div>
        </div>
      </section>

      {/* ── Company Grid ─────────────────────────────────── */}
      <section className="py-20 bg-slate-50">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">Covered Companies</h2>
              <p className="text-slate-500 mt-1 text-sm">
                8 Malaysian Blue-Chip companies across 5 sectors
              </p>
            </div>
            <Link
              href="/companies"
              className="text-sm font-medium text-blue-600 hover:text-blue-700"
            >
              View all →
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {COMPANIES.map((c) => (
              <Link key={c.ticker} href={`/companies/${c.ticker}`}>
                <div className="rounded-xl border border-slate-200 bg-white p-4 text-center hover:border-blue-300 hover:shadow-md transition-all group">
                  <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600 text-white text-xs font-bold group-hover:bg-blue-700 transition-colors">
                    {c.ticker.slice(0, 2)}
                  </div>
                  <p className="mt-2 text-xs font-bold text-slate-900">{c.ticker}</p>
                  <p className="text-xs text-slate-400 truncate">{c.name}</p>
                  <p className="mt-1 text-xs text-slate-500">{c.sector}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────── */}
      <section className="bg-blue-600 py-16 text-white text-center">
        <div className="mx-auto max-w-2xl px-4">
          <h2 className="text-2xl font-bold">Start exploring financial data</h2>
          <p className="mt-3 text-blue-100">
            Browse company profiles with interactive charts and detailed income statement data.
          </p>
          <Link
            href="/companies"
            className="mt-6 inline-block rounded-lg bg-white px-8 py-3 text-sm font-semibold text-blue-600 hover:bg-blue-50 transition-colors"
          >
            Browse Companies →
          </Link>
        </div>
      </section>
    </div>
  );
}
