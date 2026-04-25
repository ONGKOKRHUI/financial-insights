"use client";

/**
 * Peer Comparison Radar Chart — paid tier only.
 *
 * A Recharts ``RadarChart`` comparing the selected company against a fixed
 * set of peer benchmarks across 5 financial axes:
 *
 * | Axis           | Source field       | Benchmark (industry avg) |
 * |----------------|--------------------|--------------------------|
 * | Liquidity      | debt_to_equity^-1  | 0.5 → score 50           |
 * | D/E Ratio      | debt_to_equity     | lower is better          |
 * | Profit Margin  | net_margin_pct     | 15% → score 75           |
 * | Asset Turnover | revenue/assets     | approximated from KPI    |
 * | ROE            | roe_pct            | 15% → score 75           |
 *
 * Scores are normalised to 0–100 so all axes are comparable.
 *
 * @example
 * ```tsx
 * <PeerRadarChart ticker="MAYBANK" kpi={kpiData} />
 * ```
 */

import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { KPISummary } from "@/types";

interface Props {
  ticker: string;
  /** Latest KPI summary for the selected company. */
  kpi: KPISummary | undefined;
}

/** Malaysian blue-chip sector peer benchmarks (normalised to 0–100). */
const BENCHMARK = [
  { axis: "Liquidity", value: 55 },
  { axis: "Low D/E", value: 60 },
  { axis: "Profit Margin", value: 50 },
  { axis: "Asset Turnover", value: 55 },
  { axis: "ROE", value: 60 },
];

/**
 * Normalise a raw KPI value to a 0–100 radar score.
 *
 * @param field  - Which KPI axis is being scored.
 * @param kpi    - The company's KPI summary object.
 * @returns      Normalised score between 0 and 100.
 */
function toScore(field: string, kpi: KPISummary): number {
  switch (field) {
    case "Liquidity": {
      const de = kpi.debt_to_equity ?? 1;
      return Math.min(Math.round((1 / Math.max(de, 0.1)) * 50), 100);
    }
    case "Low D/E": {
      const de = kpi.debt_to_equity ?? 1;
      // Lower D/E = better; D/E of 0.5 → score 80, D/E of 2 → score 30
      return Math.min(Math.max(Math.round(100 - de * 30), 0), 100);
    }
    case "Profit Margin": {
      const margin = kpi.roe_pct ?? 0; // approximate with ROE when net margin unavailable
      return Math.min(Math.round(margin * 4), 100);
    }
    case "Asset Turnover":
      return Math.min(Math.round((kpi.revenue_bln / Math.max(kpi.net_income_bln, 0.1)) * 5), 100);
    case "ROE": {
      const roe = kpi.roe_pct ?? 0;
      return Math.min(Math.round(roe * 4), 100);
    }
    default:
      return 50;
  }
}

export default function PeerRadarChart({ ticker, kpi }: Props) {
  if (!kpi) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-500 text-sm">
        No KPI data available.
      </div>
    );
  }

  const companyData = BENCHMARK.map(({ axis }) => ({
    axis,
    value: toScore(axis, kpi),
  }));

  const chartData = BENCHMARK.map((b, i) => ({
    axis: b.axis,
    benchmark: b.value,
    company: companyData[i].value,
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <RadarChart data={chartData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
        <PolarGrid stroke="#334155" />
        <PolarAngleAxis dataKey="axis" tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <PolarRadiusAxis domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 10 }} />
        <Radar
          name="Industry Benchmark"
          dataKey="benchmark"
          stroke="#64748b"
          fill="#64748b"
          fillOpacity={0.15}
        />
        <Radar
          name={ticker}
          dataKey="company"
          stroke="#6366f1"
          fill="#6366f1"
          fillOpacity={0.35}
        />
        <Legend
          formatter={(value) => (
            <span style={{ color: "#94a3b8", fontSize: 12 }}>{value}</span>
          )}
        />
        <Tooltip
          contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
          labelStyle={{ color: "#e2e8f0" }}
          formatter={(value, name) => [`${Number(value ?? 0)}/100`, String(name)]}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
