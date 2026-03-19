import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { PROPERTY_TYPE_COLORS, propertyTypeCategory } from "@/lib/format";

interface DonutChartProps {
  data: { name: string; value: number; code?: string }[];
  title: string;
}

const FILL_COLORS = [
  "#0C447C", "#085041", "#712B13", "#3C3489", "#72243E", "#52525B",
];

export function DonutChart({ data, title }: DonutChartProps) {
  const total = data.reduce((sum, d) => sum + d.value, 0);

  return (
    <div>
      <h3 className="text-sm font-semibold text-zinc-700 mb-2">{title}</h3>
      <div className="flex items-center gap-4">
        <div style={{ width: 180, height: 180 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                isAnimationActive={false}
                stroke="none"
              >
                {data.map((entry, i) => {
                  const cat = entry.code
                    ? propertyTypeCategory(entry.code)
                    : null;
                  const color = cat
                    ? PROPERTY_TYPE_COLORS[cat].text
                    : FILL_COLORS[i % FILL_COLORS.length];
                  return <Cell key={entry.name} fill={color} />;
                })}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0];
                  const pct = total > 0 ? (((d.value as number) / total) * 100).toFixed(1) : "0";
                  return (
                    <div className="bg-white border border-zinc-200 rounded px-2 py-1 text-xs shadow-sm">
                      <div className="font-medium">{d.name}</div>
                      <div className="text-zinc-600">{pct}%</div>
                    </div>
                  );
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-1">
          {data.map((entry, i) => {
            const cat = entry.code ? propertyTypeCategory(entry.code) : null;
            const color = cat
              ? PROPERTY_TYPE_COLORS[cat].text
              : FILL_COLORS[i % FILL_COLORS.length];
            const pct = total > 0 ? ((entry.value / total) * 100).toFixed(1) : "0";
            return (
              <div key={entry.name} className="flex items-center gap-2 text-xs">
                <span
                  className="w-2.5 h-2.5 rounded-sm shrink-0"
                  style={{ backgroundColor: color }}
                />
                <span className="text-zinc-600">
                  {entry.name} ({pct}%)
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
