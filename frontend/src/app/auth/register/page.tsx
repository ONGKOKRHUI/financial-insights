"use client";

/**
 * Registration page — ``/auth/register``.
 *
 * Submits just the email address to the BFF ``POST /api/auth/register``
 * route.  The backend generates and returns the password exactly once.
 * A modal overlay shows the generated password with a copy button — after
 * the user dismisses the modal they are redirected to ``/auth/login``.
 */

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRegister } from "@/hooks/useAuth";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [generatedPassword, setGeneratedPassword] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const register = useRegister();
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    register.mutate(
      { email },
      {
        onSuccess: (data) => {
          setGeneratedPassword(data.generated_password);
        },
      }
    );
  }

  async function handleCopy() {
    if (!generatedPassword) return;
    await navigator.clipboard.writeText(generatedPassword);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDismiss() {
    router.push("/auth/login");
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-white">Create your account</h1>
          <p className="mt-2 text-sm text-slate-400">
            Already have an account?{" "}
            <Link href="/auth/login" className="text-indigo-400 hover:underline">
              Sign in
            </Link>
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-1">
              Email address
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

          {register.error && (
            <p className="rounded-lg bg-red-900/40 border border-red-700 px-3 py-2 text-sm text-red-400">
              {register.error.message}
            </p>
          )}

          <button
            type="submit"
            disabled={register.isPending}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {register.isPending ? "Creating account…" : "Create account"}
          </button>
        </form>
      </div>

      {/* One-time password modal */}
      {generatedPassword && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
          <div className="w-full max-w-md rounded-xl border border-amber-500/40 bg-slate-900 p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-500/20 text-amber-400 text-xl">
                ⚠
              </span>
              <h2 className="text-lg font-semibold text-white">Save your password</h2>
            </div>
            <p className="mb-4 text-sm text-slate-300">
              Your account has been created. This password is shown{" "}
              <strong className="text-white">once only</strong> — it will not appear again
              after you close this dialog.
            </p>
            <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2.5">
              <code className="flex-1 break-all font-mono text-sm text-emerald-400">
                {generatedPassword}
              </code>
              <button
                onClick={handleCopy}
                className="ml-2 shrink-0 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
            <button
              onClick={handleDismiss}
              className="mt-5 w-full rounded-lg bg-slate-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-600 transition-colors"
            >
              I&apos;ve saved my password — go to login
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
