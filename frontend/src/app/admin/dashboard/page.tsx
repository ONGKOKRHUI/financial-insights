"use client";

/**
 * Admin user management dashboard — ``/admin/dashboard``.
 *
 * Accessible only to users with the ``admin`` role (enforced by middleware).
 * Displays a paginated table of all registered users with inline controls
 * to update role/active status or delete accounts.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authQueryKeys } from "@/hooks/useAuth";

interface AdminUser {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
  stripe_subscription_id: string | null;
  has_api_key: boolean;
  created_at: string;
}

interface AdminUsersResponse {
  users: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}

async function fetchAdminUsers(page: number): Promise<AdminUsersResponse> {
  const res = await fetch(`/api/admin/users?page=${page}&page_size=20`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to fetch users");
  return res.json();
}

async function updateUser(id: number, body: { role?: string; is_active?: boolean }) {
  const res = await fetch(`/api/admin/users/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "include",
  });
  if (!res.ok) throw new Error("Update failed");
  return res.json();
}

async function deleteUser(id: number) {
  const res = await fetch(`/api/admin/users/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Delete failed");
}

const ROLE_BADGE: Record<string, string> = {
  free: "bg-slate-700 text-slate-300",
  paid: "bg-indigo-900 text-indigo-300",
  admin: "bg-emerald-900 text-emerald-300",
};

export default function AdminDashboardPage() {
  const [page, setPage] = useState(1);
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: authQueryKeys.adminUsers(page),
    queryFn: () => fetchAdminUsers(page),
    staleTime: 30 * 1000,
  });

  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: { role?: string; is_active?: boolean } }) =>
      updateUser(id, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: authQueryKeys.adminUsers(page) }),
  });

  const remove = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: authQueryKeys.adminUsers(page) }),
  });

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-10">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-white">User Management</h1>
          {data && (
            <p className="mt-1 text-slate-400">{data.total} registered users</p>
          )}
        </header>

        {isLoading && (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-12 rounded-lg bg-slate-800 animate-pulse" />
            ))}
          </div>
        )}

        {isError && (
          <p className="text-red-400">Failed to load users. Make sure you have the admin role.</p>
        )}

        {data && (
          <>
            <div className="overflow-x-auto rounded-xl border border-slate-800">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900/60">
                    {["ID", "Email", "Role", "Active", "Stripe Sub", "API Key", "Created", "Actions"].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.users.map((user) => (
                    <tr key={user.id} className="border-b border-slate-800/50 bg-slate-900 hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 text-slate-400">{user.id}</td>
                      <td className="px-4 py-3 text-white font-medium">{user.email}</td>
                      <td className="px-4 py-3">
                        <select
                          value={user.role}
                          onChange={(e) =>
                            update.mutate({ id: user.id, body: { role: e.target.value } })
                          }
                          className={`rounded px-2 py-1 text-xs font-semibold border-0 cursor-pointer ${ROLE_BADGE[user.role] ?? "bg-slate-700 text-slate-300"}`}
                        >
                          <option value="free">free</option>
                          <option value="paid">paid</option>
                          <option value="admin">admin</option>
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() =>
                            update.mutate({ id: user.id, body: { is_active: !user.is_active } })
                          }
                          className={`rounded px-2 py-1 text-xs font-semibold ${
                            user.is_active
                              ? "bg-emerald-900/60 text-emerald-400 hover:bg-red-900/40 hover:text-red-400"
                              : "bg-red-900/40 text-red-400 hover:bg-emerald-900/40 hover:text-emerald-400"
                          } transition-colors`}
                        >
                          {user.is_active ? "Active" : "Inactive"}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-slate-400 font-mono text-xs">
                        {user.stripe_subscription_id
                          ? user.stripe_subscription_id.slice(0, 12) + "…"
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {user.has_api_key ? (
                          <span className="text-emerald-400">✓</span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs">
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => {
                            if (confirm(`Delete ${user.email}?`)) remove.mutate(user.id);
                          }}
                          className="rounded px-2 py-1 text-xs text-red-400 hover:bg-red-900/40 transition-colors"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-slate-500">
                Page {page} of {totalPages}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-40 transition-colors"
                >
                  ← Prev
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-40 transition-colors"
                >
                  Next →
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
