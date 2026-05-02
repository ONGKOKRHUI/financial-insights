"use client";

/**
 * Authenticated main hub — `/`.
 *
 * Company selection is intentionally centralised at `/companies`; this page is
 * only a role-aware launchpad for account, billing, API, and admin actions.
 */

import Link from "next/link";
import { useAuthStore, type UserRole } from "@/stores/authStore";

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

function HomeActionCard({
  href,
  title,
  description,
  accent = "border-indigo-500",
}: {
  href: string;
  title: string;
  description: string;
  accent?: string;
}) {
  return (
    <Link
      href={href}
      className={`group flex min-h-36 flex-col rounded-xl border-l-4 bg-slate-900 p-5 hover:bg-slate-800 transition-colors ${accent}`}
    >
      <span className="text-lg font-bold text-white group-hover:text-indigo-400 transition-colors">
        {title}
      </span>
      <span className="mt-2 text-sm leading-6 text-slate-400">{description}</span>
      <span className="mt-auto pt-4 text-xs text-indigo-400 group-hover:underline">
        Open →
      </span>
    </Link>
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
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
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
            <p className="mt-1 max-w-2xl text-slate-400">
              {isPaidOrAdmin
                ? "Open a company profile to view free analytics, then continue into advanced analytics from that company page."
                : "Browse company profiles and free analytics. Upgrade to Pro to unlock each company's advanced analytics page."}
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

        {/* ── Role-aware launchpad ──────────────────────────────── */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <HomeActionCard
            href="/companies"
            title="Companies"
            description="Browse the database-backed Malaysian blue-chip company directory and open a company profile."
          />
          <HomeActionCard
            href="/account"
            title="Account"
            description="Manage your profile and subscription-linked API access."
            accent="border-slate-500"
          />
          <HomeActionCard
            href="/api-docs"
            title="API Docs"
            description="Review the available company and financial-data endpoints."
            accent="border-emerald-500"
          />
          {!isPaidOrAdmin && (
            <HomeActionCard
              href="/upgrade"
              title="Upgrade to Pro"
              description="Unlock advanced company analytics and paid API features."
              accent="border-amber-500"
            />
          )}
          {role === "admin" && (
            <HomeActionCard
              href="/admin/dashboard"
              title="Admin Dashboard"
              description="Manage users, roles, and platform administration tasks."
              accent="border-amber-500"
            />
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

        <p className="mt-4 text-center text-xs text-slate-600">
          Company selection is centralised at{" "}
          <Link href="/companies" className="text-slate-500 hover:text-slate-400 underline">
            /companies
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
