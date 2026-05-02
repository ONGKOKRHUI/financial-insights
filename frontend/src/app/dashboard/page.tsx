/**
 * `/dashboard` — legacy redirect to the unified company directory.
 *
 * Company selection now lives at `/companies` for all users, while per-company
 * paid analytics live under `/companies/[ticker]/advanced`.
 */

import { redirect } from "next/navigation";

export default function DashboardPage() {
  redirect("/companies");
}
