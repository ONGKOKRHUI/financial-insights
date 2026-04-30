"use client";

/**
 * Login page — ``/auth/login``.
 *
 * Submits credentials to the BFF ``POST /api/auth/login`` route, which
 * proxies them to FastAPI and relays the HttpOnly cookies back to the
 * browser.  On success the user is redirected to the ``redirect`` query
 * param (if present and same-origin) or to ``/``.
 */

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useLogin } from "@/hooks/useAuth";

function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const searchParams = useSearchParams();

  // Read the ?redirect= param set by the middleware when the user hit a
  // protected page while unauthenticated.  Fall back to the home page.
  const redirectTo = searchParams.get("redirect") ?? "/";
  const login = useLogin(redirectTo);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    login.mutate({ email, password });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-1">
          Email
        </label>
        <input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          placeholder="you@example.com"
        />
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-1">
          Password
        </label>
        <input
          id="password"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          placeholder="Your generated password"
        />
      </div>

      {login.error && (
        <p className="rounded-lg bg-red-900/40 border border-red-700 px-3 py-2 text-sm text-red-400">
          {login.error.message}
        </p>
      )}

      <button
        type="submit"
        disabled={login.isPending}
        className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
      >
        {login.isPending ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-white">Sign in to FinSight</h1>
          <p className="mt-2 text-sm text-slate-400">
            Don&apos;t have an account?{" "}
            <Link href="/auth/register" className="text-indigo-400 hover:underline">
              Register
            </Link>
          </p>
        </div>

        {/* Suspense is required by Next.js because useSearchParams()
            suspends during SSR when used without a boundary. */}
        <Suspense fallback={<div className="space-y-4 animate-pulse">
          <div className="h-10 rounded-lg bg-slate-800" />
          <div className="h-10 rounded-lg bg-slate-800" />
          <div className="h-10 rounded-lg bg-slate-800" />
        </div>}>
          <LoginForm />
        </Suspense>
      </div>
    </main>
  );
}
