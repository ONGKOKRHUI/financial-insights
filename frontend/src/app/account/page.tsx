"use client";

/**
 * Account settings page — ``/account``.
 *
 * Accessible to all authenticated users (free, paid, admin).
 * Shows:
 * - Email and role badge
 * - API key management (paid/admin only)
 * - Upgrade CTA (free users only)
 * - Logout button
 */

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCurrentUser, useLogout } from "@/hooks/useAuth";
import { useAuthStore } from "@/stores/authStore";

const ROLE_COLORS: Record<string, string> = {
  free: "bg-slate-700 text-slate-300",
  paid: "bg-indigo-900 text-indigo-300",
  admin: "bg-emerald-900 text-emerald-300",
};

async function fetchApiKeyInfo() {
  const res = await fetch("/api/users/api-key", { credentials: "include" });
  if (!res.ok) throw new Error("No API key");
  return res.json() as Promise<{ key_prefix: string; created_at: string }>;
}

async function rotateApiKey() {
  const res = await fetch("/api/users/api-key", {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to rotate key");
  return res.json() as Promise<{ raw_key: string; key_prefix: string }>;
}

export default function AccountPage() {
  useCurrentUser();
  const { user } = useAuthStore();
  const logout = useLogout();
  const queryClient = useQueryClient();
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const isPaidOrAdmin = user?.role === "paid" || user?.role === "admin";

  const { data: apiKeyInfo } = useQuery({
    queryKey: ["api-key-info"],
    queryFn: fetchApiKeyInfo,
    enabled: isPaidOrAdmin,
    retry: false,
  });

  const rotate = useMutation({
    mutationFn: rotateApiKey,
    onSuccess: (data) => {
      setNewKey(data.raw_key);
      queryClient.invalidateQueries({ queryKey: ["api-key-info"] });
    },
  });

  async function handleCopy() {
    if (!newKey) return;
    await navigator.clipboard.writeText(newKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-8">Account Settings</h1>

        {/* Profile card */}
        <section className="rounded-xl border border-slate-800 bg-slate-900 p-6 mb-6">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
            Profile
          </h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-white font-medium">{user?.email ?? "—"}</p>
              <p className="text-sm text-slate-500 mt-0.5">Email address</p>
            </div>
            {user?.role && (
              <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase ${ROLE_COLORS[user.role]}`}>
                {user.role}
              </span>
            )}
          </div>
        </section>

        {/* API Key (paid/admin) */}
        {isPaidOrAdmin && (
          <section className="rounded-xl border border-slate-800 bg-slate-900 p-6 mb-6">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">
              Developer API Key
            </h2>

            {newKey ? (
              <div className="space-y-3">
                <p className="text-sm text-amber-400">
                  New key generated — copy it now. It will not be shown again.
                </p>
                <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2">
                  <code className="flex-1 break-all font-mono text-sm text-emerald-400">{newKey}</code>
                  <button
                    onClick={handleCopy}
                    className="shrink-0 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
                  >
                    {copied ? "Copied!" : "Copy"}
                  </button>
                </div>
              </div>
            ) : apiKeyInfo ? (
              <div className="flex items-center justify-between">
                <div>
                  <code className="font-mono text-sm text-slate-300">{apiKeyInfo.key_prefix}…</code>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Created {new Date(apiKeyInfo.created_at).toLocaleDateString()}
                  </p>
                </div>
                <button
                  onClick={() => rotate.mutate()}
                  disabled={rotate.isPending}
                  className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-60 transition-colors"
                >
                  {rotate.isPending ? "Rotating…" : "Rotate key"}
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-400">No active API key.</p>
                <button
                  onClick={() => rotate.mutate()}
                  disabled={rotate.isPending}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60 transition-colors"
                >
                  {rotate.isPending ? "Generating…" : "Generate key"}
                </button>
              </div>
            )}
          </section>
        )}

        {/* Upgrade CTA (free only) */}
        {user?.role === "free" && (
          <section className="rounded-xl border border-indigo-800 bg-indigo-950/40 p-6 mb-6">
            <h2 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-2">
              Upgrade to Pro
            </h2>
            <p className="text-sm text-slate-400 mb-4">
              Unlock advanced dashboards, peer comparison, AI sentiment overlays, and a developer API key.
            </p>
            <Link
              href="/upgrade"
              className="inline-block rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
            >
              View pricing →
            </Link>
          </section>
        )}

        {/* Logout */}
        <button
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
          className="rounded-lg border border-red-800 px-4 py-2 text-sm text-red-400 hover:bg-red-950/40 disabled:opacity-60 transition-colors"
        >
          {logout.isPending ? "Signing out…" : "Sign out"}
        </button>
      </div>
    </main>
  );
}
