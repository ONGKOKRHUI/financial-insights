import type { Metadata } from "next";
import CompanyCard from "@/components/ui/CompanyCard";
import type { CompanySummary } from "@/types";

export const metadata: Metadata = {
  title: "Companies",
  description:
    "Browse all covered Malaysian Blue-Chip companies with financial KPIs and interactive charts.",
};

export const revalidate = 3600;
export const dynamic = "force-dynamic";

async function getCompanies(): Promise<CompanySummary[]> {
  const apiUrl = process.env.INTERNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/companies`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

const SECTOR_ORDER = [
  "Financials",
  "Energy",
  "Utilities",
  "Communication Services",
  "Consumer Discretionary",
  "Real Estate",
];

export default async function CompaniesPage() {
  const companies = await getCompanies();

  const bySector = SECTOR_ORDER.reduce<Record<string, CompanySummary[]>>(
    (acc, sector) => {
      const group = companies.filter((c) => c.sector === sector);
      if (group.length > 0) acc[sector] = group;
      return acc;
    },
    {}
  );

  const ungrouped = companies.filter(
    (c) => !SECTOR_ORDER.includes(c.sector)
  );
  if (ungrouped.length > 0) bySector["Other"] = ungrouped;

  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      {/* Page header */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-slate-900">Companies</h1>
        <p className="mt-2 text-slate-500">
          {companies.length} Malaysian Blue-Chip companies across {Object.keys(bySector).length} sectors.
          Click any company for detailed financials and interactive charts.
        </p>
      </div>

      {/* Summary stats */}
      <div className="mb-10 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Companies" value={String(companies.length)} />
        <StatCard label="Sectors" value={String(Object.keys(bySector).length)} />
        <StatCard label="Years of Data" value="5" />
        <StatCard label="Data Points" value={String(companies.length * 5 * 8)} />
      </div>

      {/* Companies by sector */}
      <div className="space-y-10">
        {Object.entries(bySector).map(([sector, group]) => (
          <div key={sector}>
            <div className="flex items-center gap-3 mb-4">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
                {sector}
              </h2>
              <div className="h-px flex-1 bg-slate-200" />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {group.map((company) => (
                <CompanyCard key={company.ticker} company={company} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      <p className="mt-0.5 text-xs text-slate-500">{label}</p>
    </div>
  );
}
