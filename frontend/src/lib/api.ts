/**
 * Centralised API client for the FinSight frontend.
 *
 * All requests are sent to Next.js BFF routes (``/api/**``), which proxy
 * them to the FastAPI backend.  This ensures:
 * - The backend URL stays server-side only (not exposed to the browser).
 * - HttpOnly auth cookies are forwarded correctly on the same origin.
 * - A single place to add request interceptors, error handling, or retries.
 *
 * Phase 4 additions
 * -----------------
 * - ``api.auth``   — register, login, refresh, logout
 * - ``api.user``   — profile and API key management
 * - ``api.search`` — unified search (requires auth)
 * - ``api.stripe`` — Stripe Checkout redirect helper
 */

import type {
  CompanySummary,
  CompanyDetail,
  KPISummary,
  IncomeStatementResponse,
} from "@/types";

const BASE = "/api";

// ---------------------------------------------------------------------------
// Generic helpers
// ---------------------------------------------------------------------------

/**
 * Fetch JSON from a BFF route with Next.js ISR revalidation.
 *
 * @param path       - Path relative to ``/api`` (e.g. ``"/companies"``).
 * @param revalidate - Cache revalidation interval in seconds (default 3600).
 * @returns          Parsed JSON of type ``T``.
 * @throws           Error if the response status is not OK.
 */
async function fetchJSON<T>(path: string, revalidate = 3600): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { next: { revalidate } });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

/**
 * Send a JSON POST/PATCH/DELETE to a BFF route (no cache).
 *
 * @param path   - Path relative to ``/api``.
 * @param method - HTTP method (default ``"POST"``).
 * @param body   - Optional JSON-serialisable request body.
 * @returns      Parsed JSON of type ``T``, or ``null`` for 204 responses.
 * @throws       Error with the backend's ``detail`` message on failure.
 */
async function mutateJSON<T>(
  path: string,
  method: "POST" | "PATCH" | "DELETE" = "POST",
  body?: unknown
): Promise<T | null> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? `API error ${res.status}`);
  return data as T;
}

// ---------------------------------------------------------------------------
// Public API object
// ---------------------------------------------------------------------------

export const api = {
  // ---- Public company & financial data (no auth required) ----------------
  companies: {
    /** List all covered companies. */
    list: () => fetchJSON<CompanySummary[]>("/companies"),
    /** Get full company profile by ticker. */
    get: async (ticker: string) => {
      const data = await fetchJSON<{ company: CompanyDetail }>(`/companies/${ticker}`);
      return data.company;
    },
    /** Get latest KPI summary by ticker. */
    summary: (ticker: string) => fetchJSON<KPISummary>(`/companies/${ticker}/summary`),
  },

  financials: {
    /** Get income statement history for a company. */
    incomeStatement: (ticker: string) =>
      fetchJSON<IncomeStatementResponse>(`/financials/${ticker}`),
  },

  // ---- Auth (Phase 4) -----------------------------------------------------
  auth: {
    /**
     * Register a new free account.  The backend generates the password.
     *
     * @param email - The user's email address.
     * @returns     Object with ``email``, ``generated_password``, and ``message``.
     */
    register: (email: string) =>
      mutateJSON<{ email: string; generated_password: string; message: string }>(
        "/auth/register",
        "POST",
        { email }
      ),

    /**
     * Log in and receive HttpOnly cookies.
     *
     * @param email    - User's email.
     * @param password - Generated password from registration.
     * @returns        Object with ``email``, ``role``, and ``message``.
     */
    login: (email: string, password: string) =>
      mutateJSON<{ email: string; role: string; message: string }>(
        "/auth/login",
        "POST",
        { email, password }
      ),

    /** Refresh the access token using the refresh cookie. */
    refresh: () => mutateJSON<{ message: string }>("/auth/refresh"),

    /** Revoke the refresh token and clear cookies. */
    logout: () => mutateJSON<null>("/auth/logout"),
  },

  // ---- Authenticated user (Phase 4) ----------------------------------------
  user: {
    /** Get the current user's profile (requires session cookie). */
    me: () =>
      fetch(`${BASE}/auth/me`, { credentials: "include", cache: "no-store" }).then((r) =>
        r.ok ? r.json() : null
      ),

    /** Get API key prefix info (paid/admin only). */
    apiKeyInfo: () => fetchJSON<{ key_prefix: string; created_at: string }>("/users/api-key"),

    /** Rotate/generate a new API key (paid/admin only). */
    rotateApiKey: () =>
      mutateJSON<{ raw_key: string; key_prefix: string; message: string }>(
        "/users/api-key",
        "POST"
      ),
  },

  // ---- Stripe (Phase 4) ----------------------------------------------------
  stripe: {
    /**
     * Create a Stripe Checkout session and redirect the browser.
     *
     * Redirects to the Stripe-hosted payment page directly.  Returns false
     * if the session could not be created.
     *
     * @returns ``true`` if redirecting, ``false`` on error.
     */
    redirectToCheckout: async (): Promise<boolean> => {
      try {
        const res = await fetch(`${BASE}/stripe/checkout`, {
          method: "POST",
          credentials: "include",
        });
        if (!res.ok) return false;
        const { checkout_url } = await res.json();
        window.location.href = checkout_url;
        return true;
      } catch {
        return false;
      }
    },
  },
};
