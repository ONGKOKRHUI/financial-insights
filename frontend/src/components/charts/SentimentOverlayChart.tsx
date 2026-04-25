"use client";

/**
 * Sentiment Overlay Chart — paid tier only.
 *
 * A Recharts ``ComposedChart`` showing:
 * - **Bar** — AI-derived sentiment score (0–100) per fiscal year.
 *   Derived from the qualitative ``future_outlook`` text via a simple
 *   keyword heuristic until Phase 5 delivers real LLM scores.
 * - **Line** — Revenue trend (MYR billions) on a secondary Y-axis.
 *
 * @example
 * ```tsx
 * <SentimentOverlayChart data={financials.data} />
 * ```
 */

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { IncomeStatementEntry } from "@/types";

interface Props {
  /** Income statement rows sorted newest-first from the backend. */
  data: IncomeStatementEntry[];
}

/**
 * Derive a mock sentiment score (0–100) from the net margin percentage.
 *
 * This placeholder maps financial performance to a sentiment proxy until
 * Phase 5 introduces real LLM-scored sentiment from earnings report text.
 *
 * @param entry - A single income statement row.
 * @returns A score between 0 and 100.
 */
function deriveSentimentScore(entry: IncomeStatementEntry): number {
  const margin = entry.net_margin_pct ?? 0;
  // Clamp margin to [0, 40] then scale to [0, 100]
  return Math.round(Math.min(Math.max(margin, 0), 40) * 2.5);
}

export default function SentimentOverlayChart({ data }: Props) {
  if (!data?.length) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-500 text-sm">
        No data available.
      </div>
    );
  }

  const chartData = [...data]
    .sort((a, b) => a.fiscal_year - b.fiscal_year)
    .map((entry) => ({
      year: entry.fiscal_year,
      sentiment: deriveSentimentScore(entry),
      revenue: entry.revenue_bln,
    }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="year" tick={{ fill: "#94a3b8", fontSize: 12 }} />
        {/* Left axis: sentiment score */}
        <YAxis
          yAxisId="sentiment"
          domain={[0, 100]}
          tick={{ fill: "#94a3b8", fontSize: 12 }}
          label={{
            value: "Sentiment",
            angle: -90,
            position: "insideLeft",
            fill: "#64748b",
            fontSize: 11,
          }}
        />
        {/* Right axis: revenue in billions */}
        <YAxis
          yAxisId="revenue"
          orientation="right"
          tickFormatter={(v: number) => `${v.toFixed(0)}B`}
          tick={{ fill: "#94a3b8", fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
          labelStyle={{ color: "#e2e8f0" }}
          formatter={(value, name) => {
            const v = Number(value ?? 0);
            const n = String(name);
            return [
              n === "sentiment" ? `${v}/100` : `MYR ${v.toFixed(1)}B`,
              n === "sentiment" ? "AI Sentiment" : "Revenue",
            ];
          }}
        />
        <Legend
          formatter={(value) => (
            <span style={{ color: "#94a3b8", fontSize: 12 }}>
              {value === "sentiment" ? "AI Sentiment Score" : "Revenue (MYR B)"}
            </span>
          )}
        />
        <Bar yAxisId="sentiment" dataKey="sentiment" fill="#6366f1" opacity={0.8} radius={[4, 4, 0, 0]} />
        <Line
          yAxisId="revenue"
          type="monotone"
          dataKey="revenue"
          stroke="#10b981"
          strokeWidth={2}
          dot={{ r: 4, fill: "#10b981" }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
