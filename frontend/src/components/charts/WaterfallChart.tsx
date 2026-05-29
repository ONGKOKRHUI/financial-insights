"use client";

/**
 * Waterfall Revenue-to-Net-Income Chart — paid tier only.
 *
 * Visualises how revenue flows down to net income through deductions.
 * Uses a Recharts ``BarChart`` with stacked bars: a transparent "spacer"
 * bar positions each segment at the correct cumulative offset, and a
 * coloured "value" bar represents the actual amount.
 *
 * Waterfall steps:
 * 1. Revenue (starting total)
 * 2. Cost of revenue  (deduction: Revenue − Gross Profit)
 * 3. Gross Profit (net so far)
 * 4. Operating expenses (deduction: Gross Profit − Operating Income)
 * 5. Operating Income
 * 6. Other deductions (Operating Income − Net Income)
 * 7. Net Income (final result)
 *
 * @example
 * ```tsx
 * <WaterfallChart data={financials.data[0]} currency="MYR" />
 * ```
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { IncomeStatementEntry } from "@/types";

interface Props {
  /** The most recent income statement row. */
  data: IncomeStatementEntry | undefined;
  /** Currency code (e.g. ``"MYR"``) for axis labels. */
  currency: string;
}

interface WaterfallStep {
  label: string;
  value: number;    // actual bar height
  offset: number;   // invisible spacer to position the bar
  isDeduction: boolean;
  isTotal: boolean;
}

/**
 * Build the waterfall step array from a single income statement row.
 *
 * @param entry    - Income statement data row.
 * @returns        Array of {@link WaterfallStep} for the chart.
 */
function buildWaterfallSteps(entry: IncomeStatementEntry): WaterfallStep[] | null {
  const {
    revenue_bln: rev,
    gross_profit_bln: gp,
    operating_income_bln: oi,
    net_income_bln: ni,
  } = entry;

  if (rev === null || gp === null || oi === null || ni === null) {
    return null;
  }

  const cogr = rev - gp;                 // cost of revenue
  const opex = gp - oi;                  // operating expenses
  const other = oi - ni;                 // other deductions (taxes, interest)

  return [
    { label: "Revenue", value: rev, offset: 0, isDeduction: false, isTotal: true },
    { label: "Cost of Revenue", value: cogr, offset: gp, isDeduction: true, isTotal: false },
    { label: "Gross Profit", value: gp, offset: 0, isDeduction: false, isTotal: true },
    { label: "Opex", value: opex, offset: oi, isDeduction: true, isTotal: false },
    { label: "Operating Income", value: oi, offset: 0, isDeduction: false, isTotal: true },
    { label: "Other", value: other, offset: ni, isDeduction: true, isTotal: false },
    { label: "Net Income", value: ni, offset: 0, isDeduction: false, isTotal: true },
  ];
}

export default function WaterfallChart({ data, currency }: Props) {
  if (!data) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-500 text-sm">
        No data available.
      </div>
    );
  }

  const steps = buildWaterfallSteps(data);

  if (!steps) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-500 text-sm">
        Waterfall unavailable because the latest income statement has missing values.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={steps} margin={{ top: 20, right: 20, bottom: 5, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: "#94a3b8", fontSize: 11 }}
          tickLine={false}
          interval={0}
          angle={-15}
          textAnchor="end"
          height={50}
        />
        <YAxis
          tickFormatter={(v: number) => `${v.toFixed(0)}B`}
          tick={{ fill: "#94a3b8", fontSize: 12 }}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
          contentStyle={{
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            borderRadius: 8,
          }}
          labelStyle={{ color: "#e2e8f0" }}
          formatter={(value, name, props): [string | null, string | null] => {
            const step = (props as { payload?: WaterfallStep }).payload;

            if (name === "offset") return [null, null];

            const v = Number(value ?? 0);
            const sign = step?.isDeduction ? "−" : "";

            return [
              `${sign}${currency} ${v.toFixed(2)}B`,
              step?.label ?? String(name),
            ];
          }}
        />
        {/* Invisible spacer bar — positions coloured bar at correct cumulative height */}
        <Bar dataKey="offset" stackId="a" fill="transparent" />
        {/* Coloured value bar */}
        <Bar dataKey="value" stackId="a" radius={[4, 4, 0, 0]}>
          {steps.map((step, index) => {
            const fill = step.isTotal
              ? step.label === "Revenue"
                ? "#3b82f6"
                : step.label === "Net Income"
                ? "#10b981"
                : "#6366f1"
              : "#ef4444";
            return <Cell key={index} fill={fill} fillOpacity={0.85} />;
          })}
          <LabelList
            dataKey="value"
            position="top"
            formatter={(v: unknown): string => {
              if (v === null || v === undefined || v === false) return "";

              // Handle bigint explicitly (this is your current error)
              if (typeof v === "bigint") return v.toString();

              const num = typeof v === "number" ? v : Number(v);

              if (!Number.isFinite(num)) return "";

              return `${num.toFixed(1)}B`;
            }}
            style={{ fill: "#94a3b8", fontSize: 10 }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
