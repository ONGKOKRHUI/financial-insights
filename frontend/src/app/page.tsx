"use client";

/**
 * Authenticated main hub — `/`.
 *
 * Entry point for all authenticated users after login.  Renders a
 * role-differentiated view of the platform:
 *
 * - **free**  — Company overview grid with analytics tiles locked behind
 *               an upgrade prompt.
 * - **paid**  — Full grid with deep-links to per-company pro analytics at
 *               `/dashboard/[ticker]`.
 * - **admin** — Same as paid, plus a prominent Admin Dashboard card.
 *
 * Auth hydration is handled by `SessionHydrator` in `providers.tsx`; this
 * page reads the already-hydrated store directly via `useAuthStore`.
 */

import Link from "next/link";
import { useAuthStore, type UserRole } from "@/stores/authStore";

const COMPANIES = [
  { ticker: "MAYBANK", name: "Malayan Banking", sector: "Financials" },
  { ticker: "CIMB", name: "CIMB Group", sector: "Financials" },
  { ticker: "TNB", name: "Tenaga Nasional", sector: "Utilities" },
  { ticker: "PCHEM", name: "Petronas Chemicals", sector: "Materials" },
  { ticker: "AXIATA", name: "Axiata Group", sector: "Communication" },
  { ticker: "IHH", name: "IHH Healthcare", sector: "Health Care" },
  { ticker: "PMETAL", name: "Press Metal Aluminium", sector: "Materials" },
  { ticker: "TM", name: "Telekom Malaysia", sector: "Communication" },
];

/** Tailwind border-colour by sector for card accent stripes. */
const SECTOR_COLORS: Record<string, string> = {
  Financials: "border-blue-500",
  Utilities: "border-yellow-500",
  Materials: "border-emerald-500",
  Communication: "border-purple-500",
  "Health Care": "border-rose-500",
};

/** Badge colour by role. */
const ROLE_BADGE: Record<UserRole, string> = {
  free: "bg-slate-700 text-slate-300",
  paid: "bg-indigo-900/60 text-indigo-300 border border-indigo-700",
  admin: "bg-amber-900/60 text-amber-300 border border-amber-700",
};

/** Human-readable role label. */
const ROLE_LABEL: Record<UserRole, string> = {
  free: "Free",
  paid: "Pro",
  admin: "Admin",
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/**
 * Company tile for paid / admin users.
 * Links directly to the per-company pro analytics dashboard.
 */
function PaidCompanyCard({
  ticker,
  name,
  sector,
}: {
  ticker: string;
  name: string;
  sector: string;
}) {
  return (
    <Link
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
  );
}

/**
 * Company tile for free users.
 * Navigates to the public company profile; analytics features are locked.
 */
function FreeCompanyCard({
  ticker,
  name,
  sector,
}: {
  ticker: string;
  name: string;
  sector: string;
}) {
  return (
    <div
      className={`relative flex flex-col rounded-xl border-l-4 bg-slate-900 p-5 ${
        SECTOR_COLORS[sector] ?? "border-slate-500"
      }`}
    >
      <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
        {sector}
      </span>
      <span className="mt-1 text-lg font-bold text-white">{ticker}</span>
      <span className="mt-0.5 text-sm text-slate-400">{name}</span>
      <div className="mt-4 flex items-center gap-1.5">
        <span className="text-xs text-slate-600 line-through">View analytics</span>
        <span className="rounded bg-amber-900/40 border border-amber-700/50 px-1.5 py-0.5 text-xs text-amber-400">
          Pro
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HomePage() {
  const { user, isHydrating } = useAuthStore();

  // Hydration guard — show skeleton while the session cookie is being resolved.
  if (isHydrating) {
    return (
      <main className="min-h-screen bg-slate-950 px-6 py-10">
        <div className="max-w-5xl mx-auto space-y-6">
          <div className="h-10 w-64 rounded-xl bg-slate-800 animate-pulse" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-32 rounded-xl bg-slate-800 animate-pulse" />
            ))}
          </div>
        </div>
      </main>
    );
  }

  const role = user?.role ?? "free";
  const isPaidOrAdmin = role === "paid" || role === "admin";

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10">
      <div className="max-w-5xl mx-auto">
        {/* ── Page header ──────────────────────────────────────── */}
        <header className="mb-8 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold text-white">
                Welcome back{user?.email ? `, ${user.email.split("@")[0]}` : ""}
              </h1>
              {user && (
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${ROLE_BADGE[role]}`}
                >
                  {ROLE_LABEL[role]}
                </span>
              )}
            </div>
            <p className="mt-1 text-slate-400">
              {isPaidOrAdmin
                ? "Select a company to view advanced analytics."
                : "Browse company profiles — upgrade to Pro for advanced analytics."}
            </p>
          </div>

          {/* Admin quick-link */}
          {role === "admin" && (
            <Link
              href="/admin/dashboard"
              className="self-start sm:self-auto rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-500 transition-colors"
            >
              Admin Dashboard →
            </Link>
          )}
        </header>

        {/* ── Company grid ──────────────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {COMPANIES.map(({ ticker, name, sector }) =>
            isPaidOrAdmin ? (
              <PaidCompanyCard key={ticker} ticker={ticker} name={name} sector={sector} />
            ) : (
              <FreeCompanyCard key={ticker} ticker={ticker} name={name} sector={sector} />
            )
          )}
        </div>

        {/* ── Upgrade CTA (free users only) ─────────────────────── */}
        {role === "free" && (
          <section className="mt-10 rounded-xl border border-indigo-800/50 bg-indigo-950/40 p-8 text-center">
            <h2 className="text-xl font-bold text-white">Unlock Pro Analytics</h2>
            <p className="mt-2 text-slate-400 max-w-md mx-auto">
              AI sentiment overlays, peer comparison radars, revenue waterfall charts,
              and a developer API key — all included in the Pro plan.
            </p>
            <Link
              href="/upgrade"
              className="mt-6 inline-block rounded-lg bg-indigo-600 px-8 py-3 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
            >
              View pricing →
            </Link>
          </section>
        )}

        {/* ── Free-tier public company data notice ──────────────── */}
        {role === "free" && (
          <p className="mt-4 text-center text-xs text-slate-600">
            Free accounts can browse company profiles at{" "}
            <Link href="/companies" className="text-slate-500 hover:text-slate-400 underline">
              /companies
            </Link>
            .
          </p>
        )}
      </div>
    </main>
  );
}
