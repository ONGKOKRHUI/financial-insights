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
 * | /companies/[ticker]/advanced | Requires paid OR admin role             |
 * | /dashboard/**    | Legacy paid analytics URLs; requires paid/admin |
 * | /account/**      | Requires any authenticated role                  |
 * | /admin/**        | Requires admin role only                         |
 *
 * Implementation note
 * -------------------
 * The middleware uses the JWT payload only as a lightweight auth hint.
 * Role-sensitive routes perform a server-side call to `/api/auth/me`,
 * which validates the token with the backend before applying RBAC redirects.
 *
 * The middleware redirect is a UX guard — it prevents rendering protected
 * pages for clearly unauthenticated users.  It is NOT the security boundary.
 */

import { NextRequest, NextResponse } from "next/server";

type VerifiedUser = {
  id: number;
  email: string;
  role: "free" | "paid" | "admin";
  has_api_key: boolean;
};

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
    const decoded = JSON.parse(atob(payload));
    if (decoded.exp && Date.now() / 1000 > decoded.exp) return null;
    return decoded;
  } catch {
    return null;
  }
}

/**
 * Public routes that do not require authentication.
 * The `/companies` list and per-company profile pages are intentionally
 * public. Advanced analytics under `/companies/[ticker]/advanced` are gated
 * separately below.
 */
const PUBLIC_PATHS = ["/companies"];

function isPublicCompanyPath(pathname: string): boolean {
  if (pathname === "/companies") return true;
  const parts = pathname.split("/").filter(Boolean);
  return parts.length === 2 && parts[0] === "companies";
}

function isAdvancedCompanyPath(pathname: string): boolean {
  const parts = pathname.split("/").filter(Boolean);
  return parts.length >= 3 && parts[0] === "companies" && parts[2] === "advanced";
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const token = req.cookies.get("access_token")?.value ?? null;
  const payload = token ? decodeJwtPayload(token) : null;
  const isAuthenticated = !!payload?.sub;

  // Skip middleware for non-browser requests (build, server fetch, etc.)
  const isBrowser = req.headers.get("sec-fetch-dest") !== null;

  if (!isBrowser) {
    return NextResponse.next();
  }

  // Authenticated users visiting auth pages are sent to the main hub.
  if (pathname.startsWith("/auth")) {
    if (isAuthenticated) {
      const url = req.nextUrl.clone();
      url.pathname = "/";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  // Public company directory/profile routes — no authentication required.
  if (PUBLIC_PATHS.includes(pathname) || isPublicCompanyPath(pathname)) {
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

  // Role-based redirects use backend-verified profile instead of unverified JWT claims.
  if (
    pathname.startsWith("/admin") ||
    isAdvancedCompanyPath(pathname) ||
    pathname.startsWith("/dashboard")
  ) {
    const meUrl = new URL("/api/auth/me", req.url);
    try {
      const res = await fetch(meUrl, {
        headers: { cookie: req.headers.get("cookie") ?? "" },
        cache: "no-store",
      });
      if (!res.ok) {
        const url = req.nextUrl.clone();
        url.pathname = "/auth/login";
        url.searchParams.set("redirect", pathname);
        return NextResponse.redirect(url);
      }
      const user = (await res.json()) as VerifiedUser;

      if (pathname.startsWith("/admin") && user.role !== "admin") {
        const url = req.nextUrl.clone();
        url.pathname = "/";
        return NextResponse.redirect(url);
      }

      if (
        (isAdvancedCompanyPath(pathname) || pathname.startsWith("/dashboard")) &&
        user.role !== "paid" &&
        user.role !== "admin"
      ) {
        const url = req.nextUrl.clone();
        url.pathname = "/upgrade";
        return NextResponse.redirect(url);
      }

      return NextResponse.next();
    } catch {
      const url = req.nextUrl.clone();
      url.pathname = "/auth/login";
      url.searchParams.set("redirect", pathname);
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
