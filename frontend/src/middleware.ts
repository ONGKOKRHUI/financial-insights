/**
 * Next.js Edge Middleware — global route-level access control.
 *
 * Runs at the edge (before the page is rendered) on every request that is
 * not explicitly excluded by {@link config.matcher}.
 *
 * Public routes (no auth required)
 * ---------------------------------
 * - `/auth/login`
 * - `/auth/register`
 * - `/api/**`       (BFF routes handle their own auth)
 * - `/_next/**`     (static assets)
 * - `/favicon.ico`
 *
 * Protection rules
 * ----------------
 * | Path pattern     | Rule                                             |
 * |------------------|--------------------------------------------------|
 * | ANY              | Unauthenticated → redirect to /auth/login        |
 * | /auth/**         | Authenticated → redirect to / (already logged in)|
 * | /dashboard/**    | Requires paid OR admin role                      |
 * | /account/**      | Requires any authenticated role                  |
 * | /admin/**        | Requires admin role only                         |
 *
 * Implementation note
 * -------------------
 * The middleware reads the ``access_token`` HttpOnly cookie and decodes
 * the JWT payload **without verifying the signature** (Edge runtime does
 * not have access to the secret key).  Full cryptographic verification
 * happens on the FastAPI backend for every protected API request.
 *
 * The middleware redirect is a UX guard — it prevents rendering protected
 * pages for clearly unauthenticated users.  It is NOT the security boundary.
 */

import { NextRequest, NextResponse } from "next/server";

/**
 * Decode a JWT payload from a base64url-encoded token string.
 *
 * Does NOT verify the signature — used only for role-based redirects.
 *
 * @param token - Raw JWT string from the cookie.
 * @returns Decoded payload object, or null if the token is malformed.
 */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(payload));
  } catch {
    return null;
  }
}

/**
 * Public routes that do not require authentication.
 * The `/companies` path is intentionally public — it displays company data
 * that can be fetched without credentials, and is linked to from the home
 * page for free-tier users.
 */
const PUBLIC_PATHS = ["/companies"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const token = req.cookies.get("access_token")?.value ?? null;
  const payload = token ? decodeJwtPayload(token) : null;
  // Accept any valid, decodable JWT as authenticated — the role field is used
  // only for fine-grained RBAC below, not for the authentication gate itself.
  const role = (payload?.role as string) ?? null;
  const isAuthenticated = !!(payload?.sub ?? role);

  // Authenticated users visiting auth pages are sent to the main hub.
  if (pathname.startsWith("/auth")) {
    if (isAuthenticated) {
      const url = req.nextUrl.clone();
      url.pathname = "/";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  // Public routes — no authentication required.
  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"))) {
    return NextResponse.next();
  }

  // Global gate — unauthenticated requests are handled based on the path.
  if (!isAuthenticated) {
    const url = req.nextUrl.clone();
    // Root visitors who are not logged in land on the public companies page
    // instead of the login screen.  The login page is reachable via the
    // "Sign In" button in the header.
    if (pathname === "/") {
      url.pathname = "/companies";
      return NextResponse.redirect(url);
    }
    url.pathname = "/auth/login";
    url.searchParams.set("redirect", pathname);
    return NextResponse.redirect(url);
  }

  // /admin/** — requires admin role.
  if (pathname.startsWith("/admin")) {
    if (role !== "admin") {
      const url = req.nextUrl.clone();
      url.pathname = "/";
      return NextResponse.redirect(url);
    }
  }

  // /dashboard/** — requires paid or admin role.
  if (pathname.startsWith("/dashboard")) {
    if (role !== "paid" && role !== "admin") {
      const url = req.nextUrl.clone();
      url.pathname = "/upgrade";
      return NextResponse.redirect(url);
    }
  }

  return NextResponse.next();
}

export const config = {
  /*
   * Match all request paths EXCEPT:
   * - /api/**             (BFF route handlers)
   * - /_next/static/**    (Next.js build assets)
   * - /_next/image/**     (image optimisation service)
   * - /favicon.ico
   */
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
