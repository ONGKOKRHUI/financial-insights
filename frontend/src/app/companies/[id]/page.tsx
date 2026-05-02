import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import KPICard from "@/components/ui/KPICard";
import RevenueTrendChart from "@/components/charts/RevenueTrendChart";
import IncomeBarChart from "@/components/charts/IncomeBarChart";
import MarginChart from "@/components/charts/MarginChart";
import FinancialsTable from "@/components/tables/FinancialsTable";
import { formatBillions, formatPct, sectorBadgeClass, yoyChange } from "@/lib/utils";
import type { CompanyDetail, KPISummary, IncomeStatementResponse } from "@/types";

const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

async function fetchAll(ticker: string) {
  const upper = ticker.toUpperCase();
  try {
    const [companyRes, summaryRes, financialsRes] = await Promise.all([
      fetch(`${BACKEND}/companies/${upper}`, { next: { revalidate: 3600 } }),
      fetch(`${BACKEND}/companies/${upper}/summary`, { next: { revalidate: 3600 } }),
      fetch(`${BACKEND}/financials/${upper}/income-statement`, { next: { revalidate: 3600 } }),
    ]);

    if (!companyRes.ok) return null;

    return {
      company: (await companyRes.json()) as CompanyDetail,
      summary: summaryRes.ok ? ((await summaryRes.json()) as KPISummary) : null,
      financials: financialsRes.ok
        ? ((await financialsRes.json()) as IncomeStatementResponse)
        : null,
    };
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const data = await fetchAll(id);
  if (!data) return { title: "Company Not Found" };
  return {
    title: `${data.company.ticker} — ${data.company.name}`,
    description: data.company.description.slice(0, 160),
  };
}

// Pages are rendered on first request and cached with ISR (1 hr).
// No generateStaticParams — avoids build-time dependency on the backend.
export const revalidate = 3600;
export const dynamicParams = true;

export default async function CompanyPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await fetchAll(id);
  if (!data) notFound();

  const { company, summary, financials } = data;
  const incomeData = financials?.data ?? [];

  // Compute YoY deltas from most recent two years
  const latest = incomeData.find((d) => d.fiscal_year === Math.max(...incomeData.map((x) => x.fiscal_year)));
  const prev = incomeData.find((d) => d.fiscal_year === (latest ? latest.fiscal_year - 1 : -1));

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      {/* Breadcrumb */}
      <nav className="mb-6 flex items-center gap-2 text-sm text-slate-500">
        <Link href="/" className="hover:text-slate-900">Home</Link>
        <span>/</span>
        <Link href="/companies" className="hover:text-slate-900">Companies</Link>
        <span>/</span>
        <span className="text-slate-900 font-medium">{company.ticker}</span>
      </nav>

      {/* Company header */}
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white text-lg font-bold">
            {company.ticker.slice(0, 2)}
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-bold text-slate-900">{company.name}</h1>
              <span className="font-mono text-sm text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                {company.ticker}
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2 flex-wrap text-sm text-slate-500">
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${sectorBadgeClass(company.sector)}`}>
                {company.sector}
              </span>
              <span>·</span>
              <span>{company.industry}</span>
              <span>·</span>
              <span>{company.exchange}</span>
              <span>·</span>
              <span>{company.currency}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/companies/${company.ticker}/advanced`}
            className="rounded-lg border border-indigo-200 bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
          >
            Advanced analytics
          </Link>
          <a
            href={company.website}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-600 hover:border-blue-300 hover:text-blue-600 transition-colors"
          >
            Visit Website ↗
          </a>
        </div>
      </div>

      {/* Description */}
      <div className="mb-8 rounded-xl border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-600 leading-relaxed">{company.description}</p>
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4 text-sm">
          <CompanyMeta label="Founded" value={String(company.founded)} />
          <CompanyMeta label="Headquarters" value={company.headquarters} />
          <CompanyMeta label="Employees" value={company.employees.toLocaleString("en-MY")} />
          <CompanyMeta
            label="Market Cap"
            value={formatBillions(company.market_cap_bln, company.currency)}
          />
        </div>
      </div>

      {/* KPI Cards */}
      {summary && (
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">
            Key Metrics — FY{summary.fiscal_year}
          </h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            <KPICard
              label="Revenue"
              value={formatBillions(summary.revenue_bln, company.currency)}
              delta={
                prev && latest
                  ? yoyChange(latest.revenue_bln, prev.revenue_bln)
                  : undefined
              }
              highlight
            />
            <KPICard
              label="Net Income"
              value={formatBillions(summary.net_income_bln, company.currency)}
              delta={
                prev && latest
                  ? yoyChange(latest.net_income_bln, prev.net_income_bln)
                  : undefined
              }
            />
            <KPICard
              label="EPS"
              value={`${company.currency} ${summary.eps.toFixed(2)}`}
              subtitle={`FY${summary.fiscal_year}`}
            />
            <KPICard
              label="P/E Ratio"
              value={summary.pe_ratio ? summary.pe_ratio.toFixed(1) + "×" : "N/A"}
            />
            <KPICard
              label="Return on Equity"
              value={formatPct(summary.roe_pct)}
            />
            <KPICard
              label="Debt / Equity"
              value={summary.debt_to_equity.toFixed(2) + "×"}
            />
            <KPICard
              label="Dividend Yield"
              value={summary.dividend_yield_pct ? formatPct(summary.dividend_yield_pct) : "N/A"}
            />
            <KPICard
              label="Market Cap"
              value={formatBillions(company.market_cap_bln, company.currency)}
            />
          </div>
        </div>
      )}

      {/* Charts */}
      {incomeData.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">
            Financial Trends
          </h2>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <RevenueTrendChart data={incomeData} currency={company.currency} />
            <IncomeBarChart data={incomeData} currency={company.currency} />
          </div>
          <div className="mt-4">
            <MarginChart data={incomeData} />
          </div>
        </div>
      )}

      {/* Financial Table */}
      {incomeData.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">
            Income Statement
          </h2>
          <FinancialsTable data={incomeData} currency={company.currency} />
        </div>
      )}

      {/* Data source notice */}
      <p className="text-xs text-slate-400 text-center mt-6">
        Data is illustrative and based on approximate public financial figures. Not for investment decisions.
      </p>
    </div>
  );
}

function CompanyMeta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-sm font-medium text-slate-900">{value}</p>
    </div>
  );
}
