import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

export interface DelinquencyTrendPoint {
  period: string;
  "30-day": number;
  "60-day": number;
  "90+": number;
}

interface DelinquencyLineChartProps {
  data: DelinquencyTrendPoint[];
}

export function DelinquencyLineChart({ data }: DelinquencyLineChartProps) {
  if (data.length === 0) {
    return (
      <div className="border border-zinc-200 rounded-md p-6 text-center text-sm text-zinc-400">
        No historical delinquency trend data available
      </div>
    );
  }

  return (
    <div>
      <h3 className="text-sm font-semibold text-zinc-700 mb-2">
        Delinquency Trend
      </h3>
      <div style={{ height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
            <XAxis
              dataKey="period"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tickFormatter={(v) => `${v}%`}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                return (
                  <div className="bg-white border border-zinc-200 rounded px-2 py-1 text-xs shadow-sm">
                    <div className="font-medium mb-1">{label}</div>
                    {payload.map((p) => (
                      <div key={String(p.dataKey)} style={{ color: p.color }}>
                        {String(p.dataKey)}: {(p.value as number).toFixed(2)}%
                      </div>
                    ))}
                  </div>
                );
              }}
            />
            <Legend
              iconType="line"
              wrapperStyle={{ fontSize: 11 }}
            />
            <Line
              type="monotone"
              dataKey="30-day"
              stroke="#D97706"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="60-day"
              stroke="#EA580C"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="90+"
              stroke="#DC2626"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
