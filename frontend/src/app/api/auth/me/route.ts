/**
 * BFF proxy: GET /api/auth/me → FastAPI GET /users/me
 *
 * Forwards the browser's session cookies to the backend and returns the
 * authenticated user's profile.  Returns 401 if the cookie is absent or
 * the access token has expired.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function GET(req: NextRequest) {
  const cookieHeader = req.headers.get("cookie") ?? "";
  const backendRes = await fetch(`${BACKEND}/users/me`, {
    headers: { Cookie: cookieHeader },
    cache: "no-store",
  });

  const data = await backendRes.json();
  return NextResponse.json(data, { status: backendRes.status });
}
