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

  let res: Response;
  let data: unknown;
  try {
    res = await fetch(`${BACKEND}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    const rawText = await res.text();
    try { data = JSON.parse(rawText); } catch { data = { detail: rawText }; }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ detail: `Backend unreachable: ${msg}` }, { status: 502 });
  }

  return NextResponse.json(data, { status: res.status });
}
