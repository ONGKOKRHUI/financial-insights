"use client";

/**
 * Global application header — sticky nav with auth-aware profile section.
 *
 * Behaviour by auth state
 * -----------------------
 * | State        | Right-side content                                    |
 * |--------------|-------------------------------------------------------|
 * | Hydrating    | Muted loading skeleton (no flash of wrong state)      |
 * | Unauthenticated | "Sign In" + "Get Started" buttons                 |
 * | free         | Role badge, email, "Account", "Upgrade", "Log Out"    |
 * | paid         | Role badge, email, "Account", "Pro Analytics", "Log Out" |
 * | admin        | Role badge, email, "Account", "Admin", "Log Out"      |
 *
 * Dynamic nav links
 * -----------------
 * All authenticated users see "Companies" and "API Docs".
 * Additional role-specific links are injected into the right-side area.
 *
 * The ticker search bar is always visible for authenticated users.
 */

import Link from "next/link";
import { useAuthStore, type UserRole } from "@/stores/authStore";
import { useLogout } from "@/hooks/useAuth";
import LiveSearchBox from "@/components/search/LiveSearchBox";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NAV_LINKS = [
  { href: "/companies", label: "Companies" },
  { href: "/api-docs", label: "API Docs" },
];

/** Tailwind classes for the role badge pill. */
const ROLE_BADGE_CLASS: Record<UserRole, string> = {
  free: "bg-slate-700 text-slate-300",
  paid: "bg-indigo-900/70 text-indigo-300 border border-indigo-700",
  admin: "bg-amber-900/70 text-amber-300 border border-amber-700",
};

const ROLE_LABEL: Record<UserRole, string> = {
  free: "Free",
  paid: "Pro",
  admin: "Admin",
};

// ---------------------------------------------------------------------------
// Header component
// ---------------------------------------------------------------------------

export default function Header() {
  const { user, isHydrating } = useAuthStore();
  const logout = useLogout();

  const isAuthenticated = !!user;
  const role = user?.role ?? "free";

  function handleLogout() {
    logout.mutate();
  }

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        {/* ── Logo ─────────────────────────────────────────── */}
        <Link
          href="/"
          className="flex items-center gap-2 text-xl font-bold text-white hover:text-indigo-400 transition-colors"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white text-sm font-bold">
            FS
          </span>
          FinSight
        </Link>

        {/* ── Nav links (authenticated only) ───────────────── */}
        {isAuthenticated && (
          <nav className="hidden items-center gap-6 md:flex">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm font-medium text-slate-400 hover:text-white transition-colors"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        )}

        {/* ── Right side ───────────────────────────────────── */}
        <div className="flex items-center gap-3">
          {/* Live search — authenticated only */}
          {isAuthenticated && <LiveSearchBox />}

          {/* Auth state: hydrating skeleton */}
          {isHydrating && (
            <div className="flex items-center gap-2">
              <div className="h-7 w-12 rounded bg-slate-800 animate-pulse" />
              <div className="h-7 w-20 rounded bg-slate-800 animate-pulse" />
            </div>
          )}

          {/* Auth state: unauthenticated */}
          {!isHydrating && !isAuthenticated && (
            <>
              <Link
                href="/auth/login"
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium text-slate-300 hover:border-slate-500 hover:text-white transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/auth/register"
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                Get Started
              </Link>
            </>
          )}

          {/* Auth state: authenticated user profile */}
          {!isHydrating && isAuthenticated && user && (
            <>
              {/* Role-specific action link */}
              {role === "free" && (
                <Link
                  href="/upgrade"
                  className="hidden sm:inline-flex rounded-lg border border-amber-700/50 bg-amber-900/30 px-3 py-1.5 text-xs font-semibold text-amber-400 hover:bg-amber-900/50 transition-colors"
                >
                  Upgrade →
                </Link>
              )}
              {role === "admin" && (
                <Link
                  href="/admin/dashboard"
                  className="hidden sm:inline-flex rounded-lg border border-amber-700/50 bg-amber-900/30 px-3 py-1.5 text-xs font-semibold text-amber-400 hover:bg-amber-900/50 transition-colors"
                >
                  Admin
                </Link>
              )}

              {/* Role badge + email */}
              <div className="hidden sm:flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${ROLE_BADGE_CLASS[role]}`}
                >
                  {ROLE_LABEL[role]}
                </span>
                <span className="max-w-[120px] truncate text-sm text-slate-300">
                  {user.email}
                </span>
              </div>

              {/* Account settings link */}
              <Link
                href="/account"
                className="hidden sm:inline-flex rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-white transition-colors"
              >
                Account
              </Link>

              {/* Logout */}
              <button
                onClick={handleLogout}
                disabled={logout.isPending}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-red-700 hover:text-red-400 disabled:opacity-50 transition-colors"
              >
                {logout.isPending ? "…" : "Log Out"}
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
