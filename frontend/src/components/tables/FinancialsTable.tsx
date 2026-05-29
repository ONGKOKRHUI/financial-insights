import { formatBillions, formatPct, deltaColor, yoyChange } from "@/lib/utils";
import type { IncomeStatementEntry } from "@/types";

interface FinancialsTableProps {
  data: IncomeStatementEntry[];
  currency?: string;
}

function DeltaCell({ current, previous }: { current: number; previous: number }) {
  const pct = yoyChange(current, previous);
  return (
    <span className={`text-xs font-medium ${deltaColor(pct)}`}>
      {pct >= 0 ? "+" : ""}{pct.toFixed(1)}%
    </span>
  );
}

export default function FinancialsTable({
  data,
  currency = "MYR",
}: FinancialsTableProps) {
  const sorted = [...data].sort((a, b) => b.fiscal_year - a.fiscal_year);

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <div className="border-b border-slate-100 px-5 py-4">
        <h3 className="text-sm font-semibold text-slate-700">
          Annual Income Statement ({currency})
        </h3>
        <p className="text-xs text-slate-400 mt-0.5">Values in billions</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                Metric
              </th>
              {sorted.map((row) => (
                <th
                  key={row.fiscal_year}
                  className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500"
                >
                  FY{row.fiscal_year}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            <TableRow label="Revenue" data={sorted} field="revenue_bln" format={(v) => formatBillions(v, currency)} />
            <TableRow label="Gross Profit" data={sorted} field="gross_profit_bln" format={(v) => formatBillions(v, currency)} />
            <TableRow label="Operating Income" data={sorted} field="operating_income_bln" format={(v) => formatBillions(v, currency)} />
            <TableRow label="Net Income" data={sorted} field="net_income_bln" format={(v) => formatBillions(v, currency)} highlight />
            <TableRow label="EPS (MYR)" data={sorted} field="eps" format={(v) => `${v.toFixed(2)}`} />
            <TableRow label="Gross Margin" data={sorted} field="gross_margin_pct" format={formatPct} />
            <TableRow label="Operating Margin" data={sorted} field="operating_margin_pct" format={formatPct} />
            <TableRow label="Net Margin" data={sorted} field="net_margin_pct" format={formatPct} />
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TableRow({
  label,
  data,
  field,
  format,
  highlight = false,
}: {
  label: string;
  data: IncomeStatementEntry[];
  field: keyof IncomeStatementEntry;
  format: (v: number) => string;
  highlight?: boolean;
}) {
  return (
    <tr className={highlight ? "bg-slate-50/50" : ""}>
      <td className={`px-5 py-3 font-medium ${highlight ? "text-slate-900" : "text-slate-600"}`}>
        {label}
      </td>
      {data.map((row, idx) => {
        const current = row[field];
        const next = data[idx + 1];
        const previous = next ? next[field] : null;
        const hasCurrent = typeof current === "number";
        const hasPrevious = typeof previous === "number";

        return (
          <td key={row.fiscal_year} className="px-4 py-3 text-right">
            <div className="flex flex-col items-end gap-0.5">
              <span className={highlight ? "font-semibold text-slate-900" : "text-slate-700"}>
                {hasCurrent ? format(current) : "N/A"}
              </span>
              {hasCurrent && hasPrevious && (
                <DeltaCell current={current} previous={previous} />
              )}
            </div>
          </td>
        );
      })}
    </tr>
  );
}
