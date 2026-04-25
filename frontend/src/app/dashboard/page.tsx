"use client";

/**
 * Paid dashboard overview page — ``/dashboard``.
 *
 * Displays a grid of all 8 covered companies as quick-launch tiles.
 * Accessible to users with the ``paid`` or ``admin`` role only
 * (enforced by middleware; this component also re-checks client-side
 * and renders an upgrade CTA as a safety fallback).
 */

import Link from "next/link";
import { useAuthStore } from "@/stores/authStore";
import { useCurrentUser } from "@/hooks/useAuth";

const TICKERS = [
  { ticker: "MAYBANK", name: "Malayan Banking", sector: "Financials" },
  { ticker: "CIMB", name: "CIMB Group", sector: "Financials" },
  { ticker: "TNB", name: "Tenaga Nasional", sector: "Utilities" },
  { ticker: "PCHEM", name: "Petronas Chemicals", sector: "Materials" },
  { ticker: "AXIATA", name: "Axiata Group", sector: "Communication" },
  { ticker: "IHH", name: "IHH Healthcare", sector: "Health Care" },
  { ticker: "PMETAL", name: "Press Metal Aluminium", sector: "Materials" },
  { ticker: "TM", name: "Telekom Malaysia", sector: "Communication" },
];

/** Sector colour mapping for card accent borders. */
const SECTOR_COLORS: Record<string, string> = {
  Financials: "border-blue-500",
  Utilities: "border-yellow-500",
  Materials: "border-emerald-500",
  Communication: "border-purple-500",
  "Health Care": "border-rose-500",
};

export default function DashboardPage() {
  useCurrentUser(); // hydrate auth store
  const { user } = useAuthStore();

  if (user && user.role === "free") {
    return (
      <main className="min-h-screen bg-slate-950 flex flex-col items-center justify-center px-4">
        <h1 className="text-2xl font-bold text-white mb-3">Upgrade to Pro</h1>
        <p className="text-slate-400 mb-6 text-center max-w-md">
          Advanced dashboards and analytics are available on the Pro plan.
        </p>
        <Link
          href="/upgrade"
          className="rounded-lg bg-indigo-600 px-6 py-3 font-semibold text-white hover:bg-indigo-500 transition-colors"
        >
          View pricing →
        </Link>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10">
      <div className="max-w-5xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-white">Pro Dashboard</h1>
          <p className="mt-1 text-slate-400">
            Select a company to view advanced analytics.
          </p>
        </header>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {TICKERS.map(({ ticker, name, sector }) => (
            <Link
              key={ticker}
              href={`/dashboard/${ticker}`}
              className={`group flex flex-col rounded-xl border-l-4 bg-slate-900 p-5 hover:bg-slate-800 transition-colors ${
                SECTOR_COLORS[sector] ?? "border-slate-500"
              }`}
            >
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                {sector}
              </span>
              <span className="mt-1 text-lg font-bold text-white group-hover:text-indigo-400 transition-colors">
                {ticker}
              </span>
              <span className="mt-0.5 text-sm text-slate-400">{name}</span>
              <span className="mt-4 text-xs text-indigo-400 group-hover:underline">
                View analytics →
              </span>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
