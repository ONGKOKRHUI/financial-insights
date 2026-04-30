/**
 * TanStack Query hooks for authentication operations.
 *
 * All auth requests are sent to the Next.js BFF (``/api/auth/**``) which
 * proxies them to the FastAPI backend.  This keeps the backend URL server-side
 * only and ensures cookies are set on the same origin as the frontend.
 *
 * @example
 * ```tsx
 * const { data: user, isLoading } = useCurrentUser();
 * const login = useLogin();
 * login.mutate({ email, password });
 * ```
 */

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useAuthStore, type AuthUser } from "@/stores/authStore";

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const authQueryKeys = {
  /** Key for the GET /users/me query. */
  currentUser: () => ["auth", "me"] as const,
  /** Key for admin user list (page-aware). */
  adminUsers: (page: number) => ["admin", "users", page] as const,
};

// ---------------------------------------------------------------------------
// API helpers — send to BFF routes
// ---------------------------------------------------------------------------

async function fetchCurrentUser(): Promise<AuthUser> {
  const res = await fetch("/api/auth/me", { credentials: "include" });
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

async function postLogin(body: { email: string; password: string }): Promise<AuthUser> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "include",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(err.detail ?? "Login failed");
  }
  return res.json();
}

async function postRegister(body: { email: string }): Promise<{ email: string; generated_password: string; message: string }> {
  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "include",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Registration failed" }));
    throw new Error(err.detail ?? "Registration failed");
  }
  return res.json();
}

async function postLogout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Query the authenticated user's profile from the backend.
 *
 * Keeps the Zustand store in sync via `onSuccess`/`onError` callbacks.
 * On first mount this call is used to hydrate the store (avoids stale
 * state after a page refresh where the cookie is still valid).
 *
 * @returns TanStack Query result with the current {@link AuthUser} or null.
 */
export function useCurrentUser() {
  const { setUser, clearUser, setHydrated } = useAuthStore();

  return useQuery<AuthUser | null>({
    queryKey: authQueryKeys.currentUser(),
    queryFn: async () => {
      try {
        const user = await fetchCurrentUser();
        setUser(user);
        return user;
      } catch {
        clearUser();
        return null;
      }
    },
    staleTime: 5 * 60 * 1000,  // 5 minutes — re-validate after 5 min
    gcTime: 10 * 60 * 1000,    // keep in cache for 10 minutes
    retry: false,               // don't retry auth failures
  });
}

/**
 * Mutation hook for logging in.
 *
 * On success: sets the user in the Zustand store and navigates to
 * ``redirectTo`` (if provided and same-origin) or ``/``.
 * On error: the ``error`` property of the returned mutation result contains
 * the error message to display to the user.
 *
 * @param redirectTo - Optional path to navigate to after a successful login.
 *                     Must start with ``/`` to prevent open-redirect attacks.
 *                     Defaults to ``/``.
 * @returns TanStack Query mutation result.
 */
export function useLogin(redirectTo = "/") {
  const queryClient = useQueryClient();
  const { setUser } = useAuthStore();
  const router = useRouter();

  // Guard against open-redirect: only allow relative paths.
  const safeDest = redirectTo.startsWith("/") ? redirectTo : "/";

  return useMutation({
    mutationFn: postLogin,
    onSuccess: (user) => {
      setUser(user);
      queryClient.setQueryData(authQueryKeys.currentUser(), user);
      router.push(safeDest);
    },
  });
}

/**
 * Mutation hook for creating a new free account.
 *
 * Returns the generated password in the mutation result data so the
 * caller can display it in a one-time modal.
 *
 * @returns TanStack Query mutation result with ``{ email, generated_password, message }``.
 */
export function useRegister() {
  return useMutation({
    mutationFn: postRegister,
  });
}

/**
 * Mutation hook for logging out.
 *
 * Clears the auth store, invalidates the current user query, and
 * redirects to the login page.
 *
 * @returns TanStack Query mutation result.
 */
export function useLogout() {
  const queryClient = useQueryClient();
  const { clearUser } = useAuthStore();
  const router = useRouter();

  return useMutation({
    mutationFn: postLogout,
    onSuccess: () => {
      clearUser();
      queryClient.removeQueries({ queryKey: authQueryKeys.currentUser() });
      router.push("/auth/login");
    },
  });
}
