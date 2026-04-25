"use client";

/**
 * Per-company paid analytics page — ``/dashboard/[ticker]``.
 *
 * Shows the three paid-tier visualizations:
 * 1. Sentiment Overlay Chart
 * 2. Peer Comparison Radar Chart
 * 3. Waterfall Revenue-to-Net-Income Chart
 *
 * Data is fetched from the FastAPI backend via Next.js BFF routes
 * using TanStack Query.
 */

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import SentimentOverlayChart from "@/components/charts/SentimentOverlayChart";
import PeerRadarChart from "@/components/charts/PeerRadarChart";
import WaterfallChart from "@/components/charts/WaterfallChart";

interface PageProps {
  params: Promise<{ ticker: string }>;
}

async function fetchIncomeStatement(ticker: string) {
  const res = await fetch(`/api/financials/${ticker}`, { credentials: "include" });
  if (!res.ok) throw new Error("Failed to fetch income data");
  return res.json();
}

async function fetchKPI(ticker: string) {
  const res = await fetch(`/api/companies/${ticker}/summary`, { credentials: "include" });
  if (!res.ok) throw new Error("Failed to fetch KPI");
  return res.json();
}

export default function PaidDashboardPage({ params }: PageProps) {
  const { ticker } = use(params);
  const upperTicker = ticker.toUpperCase();

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

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <nav className="mb-6 text-sm text-slate-500">
          <Link href="/dashboard" className="hover:text-white transition-colors">
            Dashboard
          </Link>
          {" / "}
          <span className="text-white">{upperTicker}</span>
        </nav>

        <header className="mb-8">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-white">{upperTicker}</h1>
            <span className="rounded-full bg-indigo-900/60 border border-indigo-700 px-3 py-0.5 text-xs font-semibold text-indigo-300">
              PRO
            </span>
          </div>
          <p className="mt-1 text-slate-400">Advanced analytics dashboard</p>
        </header>

        {isLoading ? (
          <div className="space-y-6">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-72 rounded-xl bg-slate-800 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="space-y-8">
            {/* Sentiment Overlay Chart */}
            <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h2 className="mb-1 text-lg font-semibold text-white">
                LLM Sentiment Overlay
              </h2>
              <p className="mb-5 text-sm text-slate-500">
                AI-derived sentiment score from earnings reports overlaid on revenue trend.
              </p>
              <SentimentOverlayChart data={financials?.data ?? []} />
            </section>

            {/* Peer Comparison Radar */}
            <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h2 className="mb-1 text-lg font-semibold text-white">
                Peer Comparison Radar
              </h2>
              <p className="mb-5 text-sm text-slate-500">
                Five-axis comparison across Liquidity, D/E, Profit Margin, Asset Turnover, and ROE.
              </p>
              <PeerRadarChart ticker={upperTicker} kpi={kpi} />
            </section>

            {/* Waterfall Chart */}
            <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h2 className="mb-1 text-lg font-semibold text-white">
                Revenue Waterfall (Latest Year)
              </h2>
              <p className="mb-5 text-sm text-slate-500">
                How gross revenue flows down to net income through operating expenses and taxes.
              </p>
              <WaterfallChart data={financials?.data?.[0]} currency={financials?.currency ?? "MYR"} />
            </section>
          </div>
        )}
      </div>
    </main>
  );
}
