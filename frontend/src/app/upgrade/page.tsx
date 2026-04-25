"use client";

/**
 * Upgrade / pricing page — ``/upgrade``.
 *
 * Displays the Free vs Pro tier comparison cards.  Clicking "Upgrade to Pro"
 * initiates a Stripe Checkout redirect via the BFF ``/api/stripe/checkout``
 * route.
 */

import { useState } from "react";
import Link from "next/link";

const FREE_FEATURES = [
  "Public landing page & API docs",
  "Basic revenue & net income charts",
  "Latest EPS and P/E KPI cards",
  "Company profiles for 8 blue-chips",
];

const PRO_FEATURES = [
  "Everything in Free",
  "AI Sentiment Overlay chart",
  "Peer Comparison Radar (5 axes)",
  "Revenue Waterfall breakdown",
  "1 developer API key",
  "Advanced search endpoint",
  "Priority support",
];

async function createCheckoutSession(): Promise<{ checkout_url: string }> {
  const res = await fetch("/api/stripe/checkout", {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to initiate checkout");
  return res.json();
}

export default function UpgradePage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpgrade() {
    setLoading(true);
    setError(null);
    try {
      const { checkout_url } = await createCheckoutSession();
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-16">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-white">Simple, transparent pricing</h1>
          <p className="mt-3 text-lg text-slate-400">
            Start free. Upgrade when you need the analytical edge.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Free tier */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-8">
            <div className="mb-6">
              <h2 className="text-xl font-bold text-white">Free</h2>
              <div className="mt-2 flex items-baseline gap-1">
                <span className="text-4xl font-bold text-white">MYR 0</span>
                <span className="text-slate-500">/month</span>
              </div>
              <p className="mt-2 text-sm text-slate-400">No credit card required.</p>
            </div>
            <ul className="space-y-3 mb-8">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-slate-300">
                  <span className="text-emerald-400 mt-0.5">✓</span>
                  {f}
                </li>
              ))}
            </ul>
            <Link
              href="/auth/register"
              className="block w-full rounded-lg border border-slate-700 px-4 py-3 text-center text-sm font-semibold text-white hover:bg-slate-800 transition-colors"
            >
              Get started free
            </Link>
          </div>

          {/* Pro tier */}
          <div className="relative rounded-2xl border border-indigo-500 bg-slate-900 p-8">
            <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-indigo-600 px-3 py-0.5 text-xs font-semibold text-white">
              Most popular
            </span>
            <div className="mb-6">
              <h2 className="text-xl font-bold text-white">Pro</h2>
              <div className="mt-2 flex items-baseline gap-1">
                <span className="text-4xl font-bold text-white">MYR 29</span>
                <span className="text-slate-500">/month</span>
              </div>
              <p className="mt-2 text-sm text-slate-400">Cancel anytime.</p>
            </div>
            <ul className="space-y-3 mb-8">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-slate-300">
                  <span className="text-indigo-400 mt-0.5">✓</span>
                  {f}
                </li>
              ))}
            </ul>
            {error && (
              <p className="mb-3 text-sm text-red-400">{error}</p>
            )}
            <button
              onClick={handleUpgrade}
              disabled={loading}
              className="w-full rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Redirecting to Stripe…" : "Upgrade to Pro →"}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
