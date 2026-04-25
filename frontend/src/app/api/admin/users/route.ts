/**
 * BFF proxy: GET /api/admin/users → FastAPI GET /admin/users
 *
 * Forwards the admin session cookie and the pagination query params.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function GET(req: NextRequest) {
  const cookieHeader = req.headers.get("cookie") ?? "";
  const { searchParams } = new URL(req.url);
  const page = searchParams.get("page") ?? "1";
  const pageSize = searchParams.get("page_size") ?? "20";

  const res = await fetch(
    `${BACKEND}/admin/users?page=${page}&page_size=${pageSize}`,
    { headers: { Cookie: cookieHeader }, cache: "no-store" }
  );
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
