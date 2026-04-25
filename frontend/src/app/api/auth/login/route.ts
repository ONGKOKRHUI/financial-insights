/**
 * BFF proxy: POST /api/auth/login → FastAPI POST /auth/login
 *
 * Forwards credentials to the backend and relays the HttpOnly Set-Cookie
 * headers to the browser.  Cookies are scoped to the frontend origin so
 * they are sent automatically on all subsequent requests.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const backendRes = await fetch(`${BACKEND}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });

  const data = await backendRes.json();
  const nextRes = NextResponse.json(data, { status: backendRes.status });

  // Relay Set-Cookie headers from the backend onto the browser response
  const setCookie = backendRes.headers.getSetCookie?.() ?? [];
  setCookie.forEach((cookie) => nextRes.headers.append("Set-Cookie", cookie));

  return nextRes;
}
