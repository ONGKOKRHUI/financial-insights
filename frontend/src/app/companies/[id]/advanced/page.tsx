"use client";

/**
 * Per-company advanced analytics page — `/companies/[id]/advanced`.
 *
 * This page reuses the existing paid-tier visualisations, but the route now
 * sits under the public company profile so `/companies` is the single company
 * entry point for every user tier.
 */

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import SentimentOverlayChart from "@/components/charts/SentimentOverlayChart";
import PeerRadarChart from "@/components/charts/PeerRadarChart";
import WaterfallChart from "@/components/charts/WaterfallChart";
import type { IncomeStatementResponse, KPISummary } from "@/types";

interface PageProps {
  params: Promise<{ id: string }>;
}

async function fetchIncomeStatement(ticker: string): Promise<IncomeStatementResponse> {
  const res = await fetch(`/api/financials/${ticker}`, { credentials: "include" });
  if (!res.ok) throw new Error("Failed to fetch income data");
  return res.json();
}

async function fetchKPI(ticker: string): Promise<KPISummary> {
  const res = await fetch(`/api/companies/${ticker}/summary`, { credentials: "include" });
  if (!res.ok) throw new Error("Failed to fetch KPI");
  return res.json();
}

export default function AdvancedCompanyAnalyticsPage({ params }: PageProps) {
  const { id } = use(params);
  const upperTicker = id.toUpperCase();

  const { data: financials, isLoading: loadingFinancials } = useQuery({
    queryKey: ["financials", upperTicker],
    queryFn: () => fetchIncomeStatement(upperTicker),
    staleTime: 5 * 60 * 1000,
  });

  const { data: kpi, isLoading: loadingKPI } = useQuery({
    queryKey: ["kpi", upperTicker],
    queryFn: () => fetchKPI(upperTicker),
    staleTime: 5 * 60 * 1000,
  });

  const isLoading = loadingFinancials || loadingKPI;
  const latestIncome = financials?.data?.at(-1);

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <nav className="mb-6 text-sm text-slate-500">
          <Link href="/companies" className="hover:text-white transition-colors">
            Companies
          </Link>
          {" / "}
          <Link
            href={`/companies/${upperTicker}`}
            className="hover:text-white transition-colors"
          >
            {upperTicker}
          </Link>
          {" / "}
          <span className="text-white">Advanced</span>
        </nav>

        <header className="mb-8">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-white">{upperTicker}</h1>
            <span className="rounded-full border border-indigo-700 bg-indigo-900/60 px-3 py-0.5 text-xs font-semibold text-indigo-300">
              PRO
            </span>
          </div>
          <p className="mt-1 text-slate-400">
            Advanced analytics generated from the financial data currently stored in the database.
          </p>
        </header>

        {isLoading ? (
          <div className="space-y-6">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-72 rounded-xl bg-slate-800 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="space-y-8">
            <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h2 className="mb-1 text-lg font-semibold text-white">
                LLM Sentiment Overlay
              </h2>
              <p className="mb-5 text-sm text-slate-500">
                Sentiment proxy overlaid on revenue trend, using available income statement fields.
              </p>
              <SentimentOverlayChart data={financials?.data ?? []} />
            </section>

            <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h2 className="mb-1 text-lg font-semibold text-white">
                Peer Comparison Radar
              </h2>
              <p className="mb-5 text-sm text-slate-500">
                Normalised KPI view using the latest stored summary for this company.
              </p>
              <PeerRadarChart ticker={upperTicker} kpi={kpi} />
            </section>

            <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h2 className="mb-1 text-lg font-semibold text-white">
                Revenue Waterfall (Latest Year)
              </h2>
              <p className="mb-5 text-sm text-slate-500">
                How revenue flows to net income through stored income statement fields.
              </p>
              <WaterfallChart data={latestIncome} currency={financials?.currency ?? "MYR"} />
            </section>
          </div>
        )}
      </div>
    </main>
  );
}
