import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { MaturityBucket } from "@/lib/types";

function formatBillions(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`;
  return `$${value.toFixed(0)}`;
}

function formatTooltipBalance(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

interface MaturityChartProps {
  data: MaturityBucket[];
}

export function MaturityChart({ data }: MaturityChartProps) {
  // Aggregate quarterly/sub-annual buckets to annual
  const annualData = useMemo(() => {
    const byYear = new Map<number, { loan_count: number; total_balance: number }>();
    for (const bucket of data) {
      const existing = byYear.get(bucket.year);
      if (existing) {
        existing.loan_count += bucket.loan_count;
        existing.total_balance += bucket.total_balance;
      } else {
        byYear.set(bucket.year, {
          loan_count: bucket.loan_count,
          total_balance: bucket.total_balance,
        });
      }
    }
    return Array.from(byYear.entries())
      .map(([year, vals]) => ({ year, ...vals }))
      .sort((a, b) => a.year - b.year);
  }, [data]);

  // Find the year with the largest balance for highlighting
  const maxYear = useMemo(() => {
    if (annualData.length === 0) return null;
    return annualData.reduce((max, d) =>
      d.total_balance > max.total_balance ? d : max
    ).year;
  }, [annualData]);

  return (
    <div>
      <h2 className="text-lg font-semibold text-zinc-800 mb-4">
        Maturity Wall
      </h2>
      <div style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={annualData}
            margin={{ top: 4, right: 4, left: 4, bottom: 4 }}
          >
            <XAxis
              dataKey="year"
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tickFormatter={formatBillions}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={64}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload as MaturityBucket;
                return (
                  <div className="bg-white border border-zinc-200 rounded px-3 py-2 text-sm shadow-sm">
                    <div className="font-medium">{d.year}</div>
                    <div className="text-zinc-600">
                      {d.loan_count} loan{d.loan_count !== 1 ? "s" : ""}
                    </div>
                    <div className="text-zinc-800 font-mono">
                      {formatTooltipBalance(d.total_balance)}
                    </div>
                  </div>
                );
              }}
            />
            <Bar dataKey="total_balance" isAnimationActive={false} radius={0}>
              {annualData.map((entry) => (
                <Cell
                  key={entry.year}
                  fill={entry.year === maxYear ? "#475569" : "#475569"}
                  fillOpacity={entry.year === maxYear ? 1 : 0.7}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
