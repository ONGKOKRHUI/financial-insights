/**
 * BFF proxy: POST /api/auth/login → FastAPI POST /auth/login
 *
 * Flow
 * ----
 * 1. Forward credentials to FastAPI and receive HttpOnly cookies.
 * 2. Extract the new access_token from the Set-Cookie headers.
 * 3. Call GET /users/me with that token to get the full user profile
 *    ({id, email, role, has_api_key}) — the bare login response only
 *    returns {email, role, message} which is insufficient for the
 *    Zustand auth store.
 * 4. Relay the Set-Cookie headers and the full profile to the browser.
 *
 * Error handling
 * --------------
 * Returns 502 if the backend is unreachable, otherwise relays the
 * backend's status code unchanged.
 */

import { NextRequest, NextResponse } from "next/server";

type AuthUser = {
  id: number;
  email: string;
  role: "free" | "paid" | "admin";
  has_api_key: boolean;
};

const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.text();

  let backendRes: Response;
  try {
    backendRes = await fetch(`${BACKEND}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: `Backend unreachable: ${msg}` }, { status: 502 });
  }

  // For error responses, relay the backend's status and error body as-is.
  if (!backendRes.ok) {
    const errData = await backendRes.json().catch(() => ({ detail: "Login failed" }));
    return NextResponse.json(errData, { status: backendRes.status });
  }

  // Collect the Set-Cookie headers to relay to the browser.
  const setCookieHeaders = backendRes.headers.getSetCookie?.() ?? [];

  // Extract the raw access_token value from the Set-Cookie header so we can
  // make a server-side /users/me call and return the full AuthUser shape
  // ({id, email, role, has_api_key}) instead of the bare login response.
  const accessTokenHeader = setCookieHeaders.find((c) => c.startsWith("access_token="));
  const accessTokenValue = accessTokenHeader?.split(";")[0].slice("access_token=".length);

  let profile: AuthUser | null = null;

  if (accessTokenValue) {
    try {
      const meRes = await fetch(`${BACKEND}/users/me`, {
        headers: { Cookie: `access_token=${accessTokenValue}` },
        cache: "no-store",
      });
      if (meRes.ok) {
        const meJson = (await meRes.json()) as Partial<AuthUser>;
        if (
          typeof meJson.id === "number" &&
          typeof meJson.email === "string" &&
          (meJson.role === "free" || meJson.role === "paid" || meJson.role === "admin") &&
          typeof meJson.has_api_key === "boolean"
        ) {
          profile = meJson as AuthUser;
        }
      }
    } catch {
      // If /users/me fails, return a hard error rather than poisoning client auth state.
    }
  }

  if (!profile) {
    return NextResponse.json(
      { detail: "Login succeeded but profile hydration failed. Please retry." },
      { status: 502 },
    );
  }

  const nextRes = NextResponse.json(profile, { status: 200 });
  setCookieHeaders.forEach((c) => nextRes.headers.append("Set-Cookie", c));
  return nextRes;
}
