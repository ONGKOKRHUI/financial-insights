"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { IncomeStatementEntry } from "@/types";

interface IncomeBarChartProps {
  data: IncomeStatementEntry[];
  currency?: string;
}

interface TooltipPayload {
  value: number | null;
  name: string;
  color: string;
}

function CustomTooltip({
  active,
  payload,
  label,
  currency,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
  currency: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-lg text-sm">
      <p className="font-semibold text-slate-900 mb-2">FY {label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }} className="flex justify-between gap-4">
          <span>{p.name}</span>
          <span className="font-medium">
            {typeof p.value === "number" ? `${currency} ${p.value.toFixed(1)}B` : "N/A"}
          </span>
        </p>
      ))}
    </div>
  );
}

export default function IncomeBarChart({
  data,
  currency = "MYR",
}: IncomeBarChartProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="text-sm font-semibold text-slate-700 mb-4">
        Income Breakdown by Year
      </h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
          <XAxis
            dataKey="fiscal_year"
            tick={{ fontSize: 12, fill: "#64748b" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 12, fill: "#64748b" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${v.toFixed(0)}B`}
          />
          <Tooltip content={<CustomTooltip currency={currency} />} />
          <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "12px" }} />
          <Bar dataKey="gross_profit_bln" name="Gross Profit" fill="#3b82f6" radius={[4, 4, 0, 0]} />
          <Bar dataKey="operating_income_bln" name="Operating Income" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
          <Bar dataKey="net_income_bln" name="Net Income" fill="#10b981" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
