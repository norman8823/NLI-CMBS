import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { fmtBalance } from "@/lib/format";

interface HBarChartProps {
  data: { name: string; value: number }[];
  title: string;
}

export function HBarChart({ data, title }: HBarChartProps) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-zinc-700 mb-2">{title}</h3>
      <div style={{ height: Math.max(200, data.length * 32 + 20) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 4, left: 0, bottom: 0 }}
          >
            <XAxis
              type="number"
              tickFormatter={(v) => fmtBalance(v)}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={36}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0];
                return (
                  <div className="bg-white border border-zinc-200 rounded px-2 py-1 text-xs shadow-sm">
                    <div className="font-medium">{d.payload.name}</div>
                    <div className="font-mono">{fmtBalance(d.value as number)}</div>
                  </div>
                );
              }}
            />
            <Bar
              dataKey="value"
              fill="#475569"
              isAnimationActive={false}
              radius={[0, 2, 2, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
