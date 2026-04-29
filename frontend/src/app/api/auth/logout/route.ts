/**
 * BFF proxy: POST /api/auth/logout → FastAPI POST /auth/logout
 *
 * Forwards the refresh_token cookie to the backend for revocation, then
 * relays the cookie-clearing Set-Cookie headers back to the browser.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function POST(req: NextRequest) {
  const cookieHeader = req.headers.get("cookie") ?? "";
  const backendRes = await fetch(`${BACKEND}/auth/logout`, {
    method: "POST",
    headers: { Cookie: cookieHeader },
  });

  const nextRes =
  backendRes.status === 204
    ? new NextResponse(null, { status: 204 })
    : NextResponse.json({}, { status: backendRes.status });
  const setCookie = backendRes.headers.getSetCookie?.() ?? [];
  setCookie.forEach((cookie) => nextRes.headers.append("Set-Cookie", cookie));

  return nextRes;
}
