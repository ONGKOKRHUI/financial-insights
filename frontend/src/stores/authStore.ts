/**
 * Global authentication state store (Zustand).
 *
 * Holds the currently authenticated user's public profile.  The store is
 * hydrated by {@link useAuth.useCurrentUser} on application mount (see
 * `src/app/layout.tsx`).  On logout the store is cleared, which triggers
 * reactive re-renders across the app.
 *
 * @example
 * ```ts
 * const { user, isLoading } = useAuthStore();
 * if (user?.role === "admin") { ... }
 * ```
 */

import { create } from "zustand";

/** Allowed user roles matching the backend RBAC model. */
export type UserRole = "free" | "paid" | "admin";

/** Subset of the backend UserProfile shape safe for client-side storage. */
export interface AuthUser {
  /** Database primary key. */
  id: number;
  email: string;
  role: UserRole;
  /** Whether the user has an active (non-revoked) API key. */
  has_api_key: boolean;
}

interface AuthStore {
  /** Currently authenticated user, or null when not logged in. */
  user: AuthUser | null;
  /**
   * True while the initial GET /users/me request is in-flight.
   * Used to suppress auth-redirect flicker on first render.
   */
  isHydrating: boolean;
  /** Replace the current user (called after login or GET /users/me). */
  setUser: (user: AuthUser) => void;
  /** Remove the current user (called after logout). */
  clearUser: () => void;
  /** Mark hydration complete (called once GET /users/me resolves). */
  setHydrated: () => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  isHydrating: true,
  setUser: (user) => set({ user, isHydrating: false }),
  clearUser: () => set({ user: null, isHydrating: false }),
  setHydrated: () => set({ isHydrating: false }),
}));
