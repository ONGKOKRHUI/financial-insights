/**
 * BFF proxy for API key management.
 *
 * GET  /api/users/api-key         → FastAPI GET  /users/me/api-key
 * POST /api/users/api-key/rotate  → handled in the [action] route
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function GET(req: NextRequest) {
  const cookieHeader = req.headers.get("cookie") ?? "";
  const res = await fetch(`${BACKEND}/users/me/api-key`, {
    headers: { Cookie: cookieHeader },
    cache: "no-store",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
  const cookieHeader = req.headers.get("cookie") ?? "";
  const res = await fetch(`${BACKEND}/users/me/api-key/rotate`, {
    method: "POST",
    headers: { Cookie: cookieHeader },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
