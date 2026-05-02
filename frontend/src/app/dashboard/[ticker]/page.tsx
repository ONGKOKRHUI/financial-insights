import { redirect } from "next/navigation";

interface PageProps {
  params: Promise<{ ticker: string }>;
}

export default async function LegacyDashboardTickerPage({ params }: PageProps) {
  const { ticker } = await params;
  redirect(`/companies/${ticker.toUpperCase()}/advanced`);
}
