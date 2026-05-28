import { NextResponse } from "next/server";

/**
 * Forward a backend fetch response to the client with the same status and body.
 * Use in BFF routes so upstream 503/500 errors are not masked as 404.
 */
export async function proxyBackendResponse(res: Response): Promise<NextResponse> {
  const text = await res.text();
  const contentType = res.headers.get("content-type") ?? "";

  if (!contentType.includes("application/json")) {
    const suspended = /suspended by its owner/i.test(text);
    const body = {
      error: suspended
        ? "Backend service is suspended on Render. Resume finsight-api in the Render dashboard, then retry."
        : text.trim().slice(0, 300) || res.statusText || "Upstream error",
      upstream_status: res.status,
    };
    return NextResponse.json(body, { status: res.status });
  }

  let body: unknown;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { error: text || res.statusText || "Upstream error", upstream_status: res.status };
  }

  if (res.ok) {
    return NextResponse.json(body);
  }

  return NextResponse.json(body, { status: res.status });
}