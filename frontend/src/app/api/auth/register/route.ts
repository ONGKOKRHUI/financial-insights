/**
 * BFF proxy: POST /api/auth/register → FastAPI POST /auth/register
 *
 * Forwards the registration request to the backend and proxies the
 * Set-Cookie headers back to the browser on the same origin.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const res = await fetch(`${BACKEND}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
