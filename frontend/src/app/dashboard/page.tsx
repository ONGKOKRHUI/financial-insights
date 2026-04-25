/**
 * `/dashboard` — permanent redirect to the authenticated hub (`/`).
 *
 * The company selection grid previously at this route has been merged into
 * the main hub at `/` so that all authenticated users (free, paid, admin)
 * have a single entry point after login.
 *
 * Per-company paid analytics remain at `/dashboard/[ticker]`.
 */

import { redirect } from "next/navigation";

export default function DashboardPage() {
  redirect("/");
}
