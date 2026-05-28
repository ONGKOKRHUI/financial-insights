import { NextRequest, NextResponse } from "next/server";
import { proxyBackendResponse } from "@/lib/proxyBackend";

// Backend API base URL (env variable or localhost fallback)
// * Priority:
// * 1. INTERNAL_API_URL (used inside cloud environments like Render/Docker networks)
// * 2. NEXT_PUBLIC_API_URL (public environment variable)
// * 3. localhost fallback for local development
const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

// Cache this route for 1 hour (ISR)
export const revalidate = 3600;

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  // Extract ticker from route param and normalize to uppercase
  const { id } = await params;
  const ticker = id.toUpperCase();

  try {
    // Request income statement from backend API
    const res = await fetch(
      `${BACKEND}/financials/${ticker}/income-statement`,
      { next: { revalidate: 3600 } }
    );

    if (!res.ok) {
      return proxyBackendResponse(res);
    }

    const data = await res.json();

    return NextResponse.json(data, {
      headers: {
        "Cache-Control":
          "public, s-maxage=3600, stale-while-revalidate=86400",
      },
    });
  } catch {
    // Backend unavailable
    return NextResponse.json(
      { error: "Backend unavailable" },
      { status: 503 }
    );
  }
}