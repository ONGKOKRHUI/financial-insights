/**
 * BFF proxy: GET /api/search/live?q=... → FastAPI GET /search/live?q=...
 *
 * Forwards the browser's HttpOnly session cookies to the backend so the
 * same auth contract as /search and /rag applies.  Caching is disabled
 * intentionally — live search results must always be fresh.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const q = searchParams.get("q") ?? "";

  if (q.trim().length < 2) {
    return NextResponse.json({ query: q, hits: [], total: 0 });
  }

  const cookieHeader = req.headers.get("cookie") ?? "";

  try {
    const backendRes = await fetch(
      `${BACKEND}/search/live?q=${encodeURIComponent(q)}`,
      {
        headers: { Cookie: cookieHeader },
        cache: "no-store",
      }
    );

    const data = await backendRes.json();
    return NextResponse.json(data, { status: backendRes.status });
  } catch {
    return NextResponse.json(
      { error: "Search service unavailable" },
      { status: 503 }
    );
  }
}
