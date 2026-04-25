# State Management

!!! success "Phase 4 Live"
    Full auth-aware state management with Zustand and TanStack Query is
    implemented in Phase 4.  Basic TanStack Query data fetching was
    available from Phase 1.

---

## State Architecture

FinSight separates state into two categories:

| Type | Tool | Examples |
|---|---|---|
| **Server state** | TanStack Query | Financial data, company lists, auth user profile |
| **Client state** | Zustand | Auth user object, search state, UI preferences |

---

## TanStack Query

### Configuration

`gcTime` and `staleTime` are configured per query type:

| Query | `staleTime` | `gcTime` | Reason |
|---|---|---|---|
| Company list | 1 hour | 2 hours | Changes only on new filing |
| Company profile | 1 hour | 2 hours | ISR-aligned |
| Income statement | 1 hour | 2 hours | Fiscal-year data |
| Current user (`/users/me`) | 5 min | 10 min | Role can change on payment |
| Admin user list | 30 sec | 1 min | Live admin operations |
| API key info | 1 min | 5 min | Rarely changes |

### Query Keys

```typescript
export const queryKeys = {
  companies: () => ["companies"] as const,
  company: (ticker: string) => ["companies", ticker] as const,
  incomeStatement: (ticker: string) => ["financials", ticker] as const,
  kpi: (ticker: string) => ["kpi", ticker] as const,
};

export const authQueryKeys = {
  currentUser: () => ["auth", "me"] as const,
  adminUsers: (page: number) => ["admin", "users", page] as const,
};
```

### Mutations

Login and logout use `useMutation` with side effects:

```typescript
// Login — sets user in Zustand store and navigates to / (main hub)
const login = useLogin();
login.mutate({ email, password });

// Logout — clears store, removes query, navigates to /auth/login
const logout = useLogout();
logout.mutate();
```

---

## Zustand Stores

### `useFinancialStore` (Phase 1)

```typescript
interface FinancialStore {
  selectedCompanyId: number | null;
  activePeriod: string;
  setSelectedCompany: (id: number) => void;
  setActivePeriod: (period: string) => void;
}
```

### `useAuthStore` (Phase 4)

```typescript
type UserRole = "free" | "paid" | "admin";

interface AuthUser {
  id: number;
  email: string;
  role: UserRole;
  has_api_key: boolean;
}

interface AuthStore {
  user: AuthUser | null;
  isHydrating: boolean;  // true until GET /users/me resolves on first mount
  setUser: (user: AuthUser) => void;
  clearUser: () => void;
  setHydrated: () => void;
}
```

**Hydration pattern** — `useCurrentUser` is called inside a dedicated
`SessionHydrator` component (see below) that is mounted in the root provider
tree on every page load.  On success it calls `setUser()`; on failure
`clearUser()`.  The `isHydrating` flag prevents auth-redirect flicker while
the initial request is in-flight.

```typescript
// Reading the store in any page or component:
const { user, isHydrating } = useAuthStore();

if (isHydrating) return <Skeleton />;
if (!user) return null; // middleware already redirected; safe fallback
```

### `SessionHydrator`

`SessionHydrator` is a lightweight client component that renders nothing but
calls `useCurrentUser()` on mount.  It is placed inside `Providers` in
`lib/providers.tsx`, which is rendered in the root `layout.tsx`.

This guarantees the auth store is hydrated on **every** page load — not just
on pages that explicitly call `useCurrentUser` — eliminating the risk of
stale state after a browser refresh on any authenticated route.

```typescript
// lib/providers.tsx
function SessionHydrator() {
  useCurrentUser(); // fires GET /api/auth/me; writes result to Zustand store
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({ ... }));
  return (
    <QueryClientProvider client={queryClient}>
      <SessionHydrator />
      {children}
    </QueryClientProvider>
  );
}
```

**Why not call `useCurrentUser` directly in `layout.tsx`?**
`layout.tsx` is a Server Component.  React Query hooks require a Client
Component context — `SessionHydrator` provides that boundary without needing
to mark the entire layout as `"use client"`.

### `searchStore` (Phase 1)

```typescript
interface SearchStore {
  query: string;
  setQuery: (q: string) => void;
}
```

---

## Data Fetching Patterns

### Financial Statements

Company profile pages use `useQuery` with ISR-aligned `staleTime`:

```typescript
const { data, isLoading } = useQuery({
  queryKey: queryKeys.incomeStatement(ticker),
  queryFn: () => api.financials.incomeStatement(ticker),
  staleTime: 60 * 60 * 1000,
});
```

### Optimistic Updates (Admin)

Admin role updates use optimistic mutations to immediately reflect the
change in the table while the PATCH request is in-flight:

```typescript
const update = useMutation({
  mutationFn: ({ id, body }) => updateUser(id, body),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: authQueryKeys.adminUsers(page) }),
});
```

### Streaming AI Responses (Phase 5)

The AI chat interface will use `EventSource` or `ReadableStream` to stream
tokens from the FastAPI backend as they are generated by the LLM.
