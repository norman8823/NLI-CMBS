import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { fmtBalance, propertyTypeCategory, PROPERTY_TYPE_COLORS, loanBalance } from "@/lib/format";
import type { Loan } from "@/lib/types";

interface MaturityWallChartProps {
  loans: Loan[];
  maturityDefault?: Loan[];
}

const TYPE_KEYS = ["Office", "Retail", "Multifamily", "Industrial", "Hotel", "Other"] as const;

export function MaturityWallChart({ loans, maturityDefault = [] }: MaturityWallChartProps) {
  const data = useMemo(() => {
    const buckets = new Map<string, Record<string, number>>();

    // Future maturing loans by quarter
    for (const loan of loans) {
      if (!loan.maturity_date) continue;
      if (loanBalance(loan) <= 0) continue;
      const d = new Date(loan.maturity_date + "T00:00:00");
      const q = Math.ceil((d.getMonth() + 1) / 3);
      const key = `${d.getFullYear()} Q${q}`;
      const balance = loanBalance(loan);
      const cat = propertyTypeCategory(loan.property_type);

      if (!buckets.has(key)) {
        buckets.set(key, { Office: 0, Retail: 0, Multifamily: 0, Industrial: 0, Hotel: 0, Other: 0, Matured: 0 });
      }
      buckets.get(key)![cat] += balance;
    }

    type BucketRow = { quarter: string; Office: number; Retail: number; Multifamily: number; Industrial: number; Hotel: number; Other: number; Matured: number };

    const sorted: BucketRow[] = Array.from(buckets.entries())
      .map(([quarter, vals]) => ({ quarter, ...vals } as BucketRow))
      .sort((a, b) => a.quarter.localeCompare(b.quarter));

    // Add maturity default as a separate "Matured" bar at the beginning
    if (maturityDefault.length > 0) {
      const maturedTotal = maturityDefault.reduce((sum, l) => sum + loanBalance(l), 0);
      if (maturedTotal > 0) {
        sorted.unshift({
          quarter: "Matured",
          Office: 0,
          Retail: 0,
          Multifamily: 0,
          Industrial: 0,
          Hotel: 0,
          Other: 0,
          Matured: maturedTotal,
        });
      }
    }

    return sorted;
  }, [loans, maturityDefault]);

  if (data.length === 0) {
    return (
      <div className="border border-zinc-200 rounded-md p-6 text-center text-sm text-zinc-400">
        No maturity data available
      </div>
    );
  }

  const hasMatured = data.some((d) => d.Matured > 0);

  return (
    <div>
      <h3 className="text-sm font-semibold text-zinc-700 mb-2">
        Maturity Wall
      </h3>
      <div style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
            <XAxis
              dataKey="quarter"
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval={0}
              angle={-45}
              textAnchor="end"
              height={50}
            />
            <YAxis
              tickFormatter={(v) => fmtBalance(v)}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={64}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                const total = payload.reduce((s, p) => s + (p.value as number), 0);
                return (
                  <div className="bg-white border border-zinc-200 rounded px-2 py-1.5 text-xs shadow-sm">
                    <div className="font-medium mb-1">{label}</div>
                    {payload
                      .filter((p) => (p.value as number) > 0)
                      .map((p) => (
                        <div key={String(p.dataKey)} className="flex justify-between gap-3">
                          <span style={{ color: p.color }}>{String(p.dataKey)}</span>
                          <span className="font-mono">{fmtBalance(p.value as number)}</span>
                        </div>
                      ))}
                    <div className="border-t border-zinc-100 mt-1 pt-1 font-medium">
                      Total: {fmtBalance(total)}
                    </div>
                  </div>
                );
              }}
            />
            <Legend iconType="square" wrapperStyle={{ fontSize: 11 }} />
            {TYPE_KEYS.map((type) => (
              <Bar
                key={type}
                dataKey={type}
                stackId="a"
                fill={PROPERTY_TYPE_COLORS[type].text}
                isAnimationActive={false}
              />
            ))}
            {hasMatured && (
              <Bar
                dataKey="Matured"
                stackId="a"
                fill="#DC2626"
                isAnimationActive={false}
              />
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
