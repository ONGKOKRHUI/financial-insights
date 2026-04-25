# Dashboard

!!! success "Phase 4 Live"
    The full paid-tier interactive dashboard is implemented in Phase 4.
    The basic public site with company profiles and free-tier charts
    is live from Phase 1.

---

## Access Control

| Page / Feature | Unauthenticated | Free | Paid | Admin |
|---|:---:|:---:|:---:|:---:|
| Landing page (`/`) | ✅ | ✅ | ✅ | ✅ |
| Company profiles (`/companies/**`) | ✅ | ✅ | ✅ | ✅ |
| Free-tier charts (Revenue, Margin, Bar) | ✅ | ✅ | ✅ | ✅ |
| KPI cards | ✅ | ✅ | ✅ | ✅ |
| Account settings (`/account`) | ❌ | ✅ | ✅ | ✅ |
| Paid dashboard (`/dashboard/**`) | ❌ | ❌ | ✅ | ✅ |
| Paid charts (Sentiment, Radar, Waterfall) | ❌ | ❌ | ✅ | ✅ |
| Admin dashboard (`/admin/dashboard`) | ❌ | ❌ | ❌ | ✅ |

---

## Free Tier Pages (Phase 1 — Live)

### Landing Page (`/`)

- Hero section with CTA buttons to `/companies` and the MAYBANK demo profile.
- Horizontal scrollable ticker strip.
- Feature highlights grid.
- API preview panel with live JSON response.
- Company grid (2×4 tiles).

### Company Profile (`/companies/[id]`)

- Breadcrumb navigation.
- Company header with sector, industry, exchange, and currency.
- Company metadata grid (founded, HQ, employees, market cap).
- Financial statements table (`FinancialsTable`) — 5-year income statement.
- **Free-tier charts** (Revenue Trend, Income Bar, Margin Chart).
- 8 KPI cards in a responsive grid.

---

## Paid Tier Dashboard (Phase 4)

### Dashboard Overview (`/dashboard`)

A company grid showing all 8 covered companies as quick-launch tiles.
Colour-coded by sector.  Requires `paid` or `admin` role — middleware
redirects `free` users to `/upgrade`.

### Per-Company Analytics (`/dashboard/[ticker]`)

Three paid-tier visualisations displayed below the existing free-tier charts.

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

## Other Authenticated Pages (Phase 4)

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

## Free-Tier Chart Components (Phase 1)

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
The Phase 1 company profile renders 8 KPI cards in a responsive grid.

---

## Performance

- **SSG & ISR:** Company listing and profiles are pre-rendered at build time.
- **Server-side data fetching:** Company profile parallelises three backend calls with `Promise.all`.
- **TanStack Query caching:** Client-side hooks cache data for 5–10 minutes with configurable `staleTime`.
- **Skeleton loading states:** `KPICardSkeleton`, `ChartSkeleton`, `TableSkeleton` prevent layout shift.
- **Responsive design:** Mobile-first breakpoints; charts use `ResponsiveContainer`; tables use `overflow-x-auto`.
