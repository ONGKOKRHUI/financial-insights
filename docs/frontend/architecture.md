# Frontend Architecture

!!! success "Phase 4 Live"
    Full authentication, RBAC-protected routes, an authenticated main hub,
    and Stripe integration are implemented in Phase 4.  Every route except
    `/auth/**` and `/api/**` is gated behind a valid session cookie.

---

## Tech Stack

| Library | Purpose |
|---|---|
| Next.js 16 (App Router) | React framework, SSR / SSG / Edge middleware |
| TypeScript | Type safety across all components and API shapes |
| Zustand | Client-side global state (auth user, UI preferences) |
| TanStack Query v5 | Server state, caching, and mutation handling |
| Recharts | Financial chart visualizations (free and paid tier) |
| Tailwind CSS v4 | Utility-first styling |
| Stripe.js | Stripe Checkout redirect for subscription upgrade |

---

## Project Structure

```
frontend/src/
├── app/
│   ├── page.tsx                          # Authenticated hub — role-aware company grid (CSR)
│   ├── layout.tsx                        # Root layout — wraps all pages in Providers
│   ├── not-found.tsx                     # 404 page
│   ├── auth/
│   │   ├── login/page.tsx                # Login form (public)
│   │   └── register/page.tsx             # Registration + one-time password modal (public)
│   ├── companies/
│   │   ├── page.tsx                      # Company listing (SSG)
│   │   └── [id]/page.tsx                 # Company profile with free-tier charts (ISR)
│   ├── dashboard/
│   │   ├── page.tsx                      # Redirect → / (hub moved to root)
│   │   └── [ticker]/page.tsx             # Per-company paid analytics (CSR)
│   ├── account/page.tsx                  # Account settings + API key (CSR)
│   ├── upgrade/page.tsx                  # Pricing cards + Stripe redirect (CSR)
│   ├── admin/
│   │   └── dashboard/page.tsx            # Admin user management (CSR)
│   └── api/                              # Next.js BFF route handlers
│       ├── auth/
│       │   ├── register/route.ts         # POST /api/auth/register
│       │   ├── login/route.ts            # POST /api/auth/login
│       │   ├── logout/route.ts           # POST /api/auth/logout
│       │   └── me/route.ts               # GET  /api/auth/me
│       ├── companies/route.ts            # GET  /api/companies
│       ├── companies/[id]/route.ts       # GET  /api/companies/{ticker}
│       ├── financials/[id]/route.ts      # GET  /api/financials/{ticker}
│       ├── users/api-key/route.ts        # GET + POST /api/users/api-key
│       ├── admin/users/route.ts          # GET  /api/admin/users
│       ├── admin/users/[id]/route.ts     # PATCH + DELETE /api/admin/users/{id}
│       ├── search/live/route.ts          # GET  /api/search/live?q= — live search BFF proxy
│       └── stripe/checkout/route.ts      # POST /api/stripe/checkout
├── components/
│   ├── charts/
│   │   ├── RevenueTrendChart.tsx         # Free: dual-line revenue & net income
│   │   ├── IncomeBarChart.tsx            # Free: grouped bar income breakdown
│   │   ├── MarginChart.tsx               # Free: area chart profitability margins
│   │   ├── SentimentOverlayChart.tsx     # PAID: AI sentiment + revenue composed chart
│   │   ├── PeerRadarChart.tsx            # PAID: 5-axis radar vs peers
│   │   └── WaterfallChart.tsx            # PAID: revenue-to-net-income waterfall
│   ├── tables/
│   │   └── FinancialsTable.tsx           # Income statement with YoY deltas
│   ├── ui/
│   │   ├── KPICard.tsx                   # Metric card with value and YoY delta
│   │   ├── CompanyCard.tsx               # Company tile for listings
│   │   ├── Skeleton.tsx                  # Loading skeleton variants
│   │   └── Badge.tsx                     # Status / sector badge
│   ├── search/
│   │   └── LiveSearchBox.tsx             # Debounced Elasticsearch live search dropdown
│   └── layout/
│       ├── Header.tsx                    # Sticky nav — auth-aware profile, live search, logout
│       └── Footer.tsx                    # Site footer
├── hooks/
│   ├── useCompanies.ts                   # TanStack Query: company data
│   ├── useFinancials.ts                  # TanStack Query: income statement
│   └── useAuth.ts                        # TanStack Query: auth mutations + currentUser
├── stores/
│   ├── searchStore.ts                    # Zustand: ticker search state
│   └── authStore.ts                      # Zustand: auth user, role, hydration flag
├── lib/
│   ├── api.ts                            # Centralised BFF fetch client
│   ├── utils.ts                          # Formatters, colour helpers, YoY calc
│   └── providers.tsx                     # QueryClientProvider + SessionHydrator
├── types/
│   └── index.ts                          # TypeScript interfaces for all API shapes
└── middleware.ts                          # Edge middleware — global route protection
```

---

## Route Protection

The Edge Middleware (`middleware.ts`) intercepts every request before the page renders.

```
matcher: "/((?!api|_next/static|_next/image|favicon.ico).*)"
```

| Condition | Action |
|---|---|
| No `access_token` cookie on any route | Redirect → `/auth/login?redirect=<path>` |
| Valid token on `/auth/**` | Redirect → `/` (already logged in) |
| Valid token, `role != admin` on `/admin/**` | Redirect → `/` |
| Valid token, `role == free` on `/dashboard/**` | Redirect → `/upgrade` |
| Any other authenticated request | Allow through |

The middleware decodes the JWT **without verifying the signature** (Edge runtime limitation).
Cryptographic verification is performed by FastAPI on every API call — the middleware is a
UX guard only, not the security boundary.

---

## Authentication Flow

```mermaid
sequenceDiagram
    participant Browser
    participant NextEdge as Next.js Edge Middleware
    participant BFF as Next.js BFF Routes
    participant FastAPI

    Browser->>NextEdge: GET / (no cookie)
    NextEdge->>NextEdge: access_token missing
    NextEdge-->>Browser: 302 → /auth/login?redirect=/

    Browser->>BFF: POST /api/auth/login {email, password}
    BFF->>FastAPI: POST /auth/login
    FastAPI-->>BFF: 200 + Set-Cookie (access_token, refresh_token)
    BFF-->>Browser: 200 + relay Set-Cookie headers

    Browser->>NextEdge: GET / (cookie present)
    NextEdge->>NextEdge: Decode JWT — role = "paid"
    NextEdge-->>Browser: Render /

    Browser->>BFF: GET /api/auth/me (SessionHydrator on mount)
    BFF->>FastAPI: GET /users/me (forward Cookie header)
    FastAPI-->>BFF: 200 {id, email, role, has_api_key}
    BFF-->>Browser: 200 {id, email, role, has_api_key}
    Browser->>Browser: setUser() in Zustand store → Header re-renders
```

---

## Rendering Strategy

| Route | Strategy | Reason |
|---|---|---|
| Main hub (`/`) | CSR | Auth-gated, role-dependent content |
| Company listing (`/companies`) | SSG | Infrequently changing list |
| Company profiles (`/companies/[id]`) | ISR (1 hr) | Refreshes on new filing |
| Auth pages (`/auth/**`) | CSR | No sensitive server-side work |
| Paid analytics (`/dashboard/[ticker]`) | CSR | Auth-gated, dynamic data |
| Account settings (`/account`) | CSR | Session-dependent |
| Admin dashboard (`/admin/**`) | CSR | Real-time user data |

---

## Live Search

### LiveSearchBox component

`src/components/search/LiveSearchBox.tsx` is a self-contained, debounced typeahead
widget rendered in the authenticated header.

**Key behaviours:**

| Behaviour | Detail |
|---|---|
| Debounce | 200 ms — no request is fired until the user pauses typing |
| Abort | Each keypress cancels the previous in-flight `fetch` via `AbortController` |
| Min length | Queries shorter than 2 characters after trimming return an empty list without hitting the backend |
| Results | Always ≤ 5, ranked by Elasticsearch BM25 relevance score |
| Keyboard | ↑ / ↓ to navigate, Enter to open, Escape to close |
| Navigation | `source_uri` from the hit (opens in new tab for external URLs); falls back to `/companies/{ticker}` for company-domain hits |
| Auth | Relies on the session cookie forwarded through the BFF route — no extra auth setup needed |

### BFF proxy

`src/app/api/search/live/route.ts` forwards `GET /api/search/live?q=...` to
FastAPI `GET /search/live?q=...` with the browser's `Cookie` header so the
backend `require_api_key_or_session` dependency is satisfied.  The route
sets `cache: "no-store"` to ensure results are never stale.

### API helper

`api.search.live(query, signal?)` in `src/lib/api.ts` wraps the BFF route and
accepts an optional `AbortSignal` so the component can cancel stale requests.

---

## Deployment

### Frontend → Vercel

The frontend is deployed to Vercel via GitHub Actions on every push to `main`
that touches `frontend/**`.

**Workflow:** `.github/workflows/deploy-frontend.yml`

**Required GitHub Secrets:**

| Secret | Description |
|---|---|
| `VERCEL_TOKEN` | Vercel personal access token |
| `VERCEL_ORG_ID` | Vercel team/org ID |
| `VERCEL_PROJECT_ID` | Vercel project ID |
| `NEXT_PUBLIC_API_URL` | Public FastAPI URL |
| `INTERNAL_API_URL` | Server-side FastAPI URL |
| `STRIPE_SECRET_KEY` | Stripe secret key (for BFF checkout) |
| `STRIPE_PRO_PRICE_ID` | Stripe price ID for MYR 29/mo plan |
| `NEXT_PUBLIC_APP_URL` | Frontend URL for Stripe redirects |

### Backend → Render

See `docs/backend/fastapi-architecture.md` for backend deployment details.
