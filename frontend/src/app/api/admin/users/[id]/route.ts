/**
 * BFF proxy for admin user operations.
 *
 * PATCH  /api/admin/users/[id] → FastAPI PATCH  /admin/users/{id}
 * DELETE /api/admin/users/[id] → FastAPI DELETE /admin/users/{id}
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookieHeader = req.headers.get("cookie") ?? "";
  const body = await req.text();
  const res = await fetch(`${BACKEND}/admin/users/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Cookie: cookieHeader },
    body,
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookieHeader = req.headers.get("cookie") ?? "";
  const res = await fetch(`${BACKEND}/admin/users/${id}`, {
    method: "DELETE",
    headers: { Cookie: cookieHeader },
  });
  return new NextResponse(null, { status: res.status });
}
