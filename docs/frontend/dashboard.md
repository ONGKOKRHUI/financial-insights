# Dashboard & Pages

!!! success "Phase 4 Live"
    `/companies` is the single company entry point for every user. Company
    profiles and free visualisations are public, while advanced analytics live
    at `/companies/[ticker]/advanced` and require `paid` or `admin`.

---

## Access Control

| Page / Feature | Unauthenticated | Free | Paid | Admin |
|---|:---:|:---:|:---:|:---:|
| Main hub (`/`) | ❌ → `/companies` | ✅ | ✅ | ✅ |
| Company directory (`/companies`) | ✅ | ✅ | ✅ | ✅ |
| Company profiles (`/companies/[ticker]`) | ✅ | ✅ | ✅ | ✅ |
| Free-tier charts (Revenue, Margin, Bar) | ✅ | ✅ | ✅ | ✅ |
| KPI cards | ✅ | ✅ | ✅ | ✅ |
| Account settings (`/account`) | ❌ → login | ✅ | ✅ | ✅ |
| Per-company paid analytics (`/dashboard/[ticker]`) | ❌ → login | ❌ → upgrade | ✅ | ✅ |
| Per-company advanced analytics (`/companies/[ticker]/advanced`) | ❌ → login | ❌ → upgrade | ✅ | ✅ |
| Paid charts (Sentiment, Radar, Waterfall) | ❌ → login | ❌ → upgrade | ✅ | ✅ |
| Admin dashboard (`/admin/dashboard`) | ❌ → login | ❌ → / | ❌ → / | ✅ |

!!! note "Global gate"
    `/companies` and `/companies/[ticker]` are public. The Edge Middleware
    protects authenticated routes and gates advanced analytics before the page
    is rendered.

---

## Main Hub (`/`)

The root page is the authenticated entry point after login. It no longer
contains a separate company grid; instead, it links users to the central
`/companies` directory plus account, API docs, upgrade, and admin actions
based on role.

---

## Per-Company Advanced Analytics (`/companies/[ticker]/advanced`)

Three paid-tier visualisations gated to `paid` and `admin` roles.
`free` users who navigate here directly are redirected to `/upgrade`.
Legacy `/dashboard/[ticker]` URLs redirect to the new route.

---

## Paid Chart Components

### Sentiment Overlay Chart (`SentimentOverlayChart.tsx`)

- **Type:** Recharts `ComposedChart` with dual Y-axes.
- **Left axis:** AI sentiment score (0–100) — `Bar` per fiscal year.
- **Right axis:** Revenue in MYR billions — `Line` overlay.
- **Sentiment source:** Derived from net margin % as a proxy until Phase 5
  delivers real LLM scores from earnings report text.
- **Use case:** Identify years where financial performance diverged from
  the tone of management commentary.

### Peer Comparison Radar (`PeerRadarChart.tsx`)

- **Type:** Recharts `RadarChart` with 5 axes.
- **Axes:** Liquidity, Low D/E, Profit Margin, Asset Turnover, ROE.
- **Data:** Latest KPI summary normalised to 0–100 per axis.
- **Benchmark:** Industry-average scores overlaid in grey.
- **Use case:** At-a-glance competitive positioning against blue-chip peers.

### Revenue Waterfall (`WaterfallChart.tsx`)

- **Type:** Recharts `BarChart` with stacked bars (spacer + value technique).
- **Steps:** Revenue → Cost of Revenue → Gross Profit → Opex → Operating Income → Other → Net Income.
- **Colours:** Blue for totals, red for deductions, green for net income.
- **Use case:** Understand exactly where revenue is consumed before reaching net income.

---

## Other Authenticated Pages

### Account Settings (`/account`)

- Email and role badge.
- API key prefix display with rotation button (paid/admin only).
- Upgrade CTA for free users.
- Sign out button.

### Upgrade / Pricing (`/upgrade`)

- Free vs Pro pricing cards (MYR 0 vs MYR 29/month).
- Pro plan: feature comparison list.
- "Upgrade to Pro" button → Stripe Checkout hosted page.

### Admin Dashboard (`/admin/dashboard`)

- Paginated user management table.
- Inline role selector (dropdown per row).
- Active/Inactive toggle button per row.
- Delete user button with confirmation.
- Stripe subscription ID and API key status columns.

---

## Company Profile (`/companies/[id]`)

Accessible to every visitor. The advanced analytics button is visible on the
profile, but only `paid` and `admin` users can reach the destination page.

- Breadcrumb navigation.
- Company header with sector, industry, exchange, and currency.
- Company metadata grid (founded, HQ, employees, market cap).
- Financial statements table (`FinancialsTable`) — 5-year income statement.
- **Free-tier charts** (Revenue Trend, Income Bar, Margin Chart).
- 8 KPI cards in a responsive grid.
- Advanced analytics CTA linking to `/companies/[ticker]/advanced`.

---

## Free-Tier Chart Components

### Revenue Trend Chart (`RevenueTrendChart.tsx`)

- **Type:** Recharts `LineChart` with `ResponsiveContainer`
- **Data:** `fiscal_year`, `revenue_bln`, `net_income_bln`
- **Lines:** Revenue (blue `#3b82f6`), Net Income (emerald `#10b981`)

### Income Bar Chart (`IncomeBarChart.tsx`)

- **Type:** Recharts `BarChart` with rounded corners
- **Data:** Gross profit, operating income, net income per year

### Margin Chart (`MarginChart.tsx`)

- **Type:** Recharts `AreaChart` with gradient fills
- **Data:** `gross_margin_pct`, `operating_margin_pct`, `net_margin_pct`

### KPI Cards (`KPICard.tsx`)

Each card displays a label, formatted value, YoY delta badge, and subtitle.
The company profile renders 8 KPI cards in a responsive grid.

---

## Performance

- **SSG & ISR:** Company listing and profiles are pre-rendered at build time.
- **Server-side data fetching:** Company profile parallelises three backend calls with `Promise.all`.
- **TanStack Query caching:** Client-side hooks cache data for 5–10 minutes with configurable `staleTime`.
- **Skeleton loading states:** `KPICardSkeleton`, `ChartSkeleton`, `TableSkeleton` prevent layout shift.
- **Responsive design:** Mobile-first breakpoints; charts use `ResponsiveContainer`; tables use `overflow-x-auto`.
