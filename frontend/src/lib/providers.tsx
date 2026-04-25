"use client";

/**
 * Global React providers for the FinSight frontend.
 *
 * Components
 * ----------
 * - `Providers`       — Root provider tree; wraps the entire app in `layout.tsx`.
 * - `SessionHydrator` — Lightweight component that calls `useCurrentUser()` on
 *                       every page load to keep the Zustand auth store in sync
 *                       with the active session cookie.
 *
 * Why SessionHydrator?
 * --------------------
 * `useCurrentUser` writes the authenticated user into the Zustand store.
 * Without a hydrator, the store is only populated on pages that explicitly
 * call the hook — meaning a browser refresh on `/` or `/companies` would
 * leave the store empty until a page that opts in is visited.
 *
 * Placing `SessionHydrator` inside `Providers` (which is rendered in the root
 * layout) guarantees the GET /api/auth/me call fires exactly once on every
 * full-page load, regardless of which route the user lands on.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { useCurrentUser } from "@/hooks/useAuth";

/**
 * Fires `useCurrentUser` on mount to hydrate the Zustand auth store.
 *
 * Renders nothing — it is a side-effect-only component.  Must be placed
 * inside `QueryClientProvider` so it can access the React Query context.
 */
function SessionHydrator() {
  useCurrentUser();
  return null;
}

/**
 * Root provider tree.
 *
 * Wraps children with:
 * 1. `QueryClientProvider` — makes TanStack Query hooks available everywhere.
 * 2. `SessionHydrator`     — hydrates the auth store on every page load.
 *
 * @param children - The page subtree rendered by `layout.tsx`.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            /**
             * Queries stay "fresh" for 60 seconds before React Query
             * automatically refetches in the background.
             */
            staleTime: 60 * 1000,
            /**
             * Retry once before surfacing an error to the UI.
             * Auth queries override this with `retry: false`.
             */
            retry: 1,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {/* Hydrates Zustand auth store from the session cookie on every load. */}
      <SessionHydrator />
      {children}
    </QueryClientProvider>
  );
}
