import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { PropertySnapshot } from "@/lib/types";

interface PropertyTrendChartsProps {
  snapshots: PropertySnapshot[];
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  const month = d.toLocaleDateString("en-US", { month: "short" });
  const year = d.getFullYear().toString().slice(2);
  return `${month} '${year}`;
}

function formatNoi(value: number): string {
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

function formatOccupancy(value: number): string {
  return `${value.toFixed(1)}%`;
}

function formatDscr(value: number): string {
  return `${value.toFixed(2)}x`;
}

export function PropertyTrendCharts({ snapshots }: PropertyTrendChartsProps) {
  // Sort by date ascending
  const sorted = [...snapshots].sort((a, b) =>
    a.reporting_period_end.localeCompare(b.reporting_period_end)
  );

  // Prepare occupancy data — normalize decimals to percentages
  const occData = sorted
    .filter((s) => s.occupancy != null)
    .map((s) => ({
      date: formatDate(s.reporting_period_end),
      value: s.occupancy! <= 1 ? s.occupancy! * 100 : s.occupancy!,
    }));

  // Prepare NOI data
  const noiData = sorted
    .filter((s) => s.noi != null)
    .map((s) => ({
      date: formatDate(s.reporting_period_end),
      value: s.noi!,
    }));

  // Prepare DSCR data
  const dscrData = sorted
    .filter((s) => s.dscr_noi != null)
    .map((s) => ({
      date: formatDate(s.reporting_period_end),
      value: s.dscr_noi!,
    }));

  const hasOcc = occData.length >= 2;
  const hasNoi = noiData.length >= 2;
  const hasDscr = dscrData.length >= 2;

  if (!hasOcc && !hasNoi && !hasDscr) {
    return (
      <div className="border border-zinc-200 rounded-md p-6 text-center text-sm text-zinc-400">
        Insufficient historical data
      </div>
    );
  }

  const tickStyle = { fontSize: 11, fill: "#71717a" };

  return (
    <div className="space-y-4">
      {(hasOcc || hasNoi) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {hasOcc && (
            <div className="border border-zinc-200 rounded-md p-4">
              <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-3">
                Occupancy Trend
              </h4>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={occData}>
                  <XAxis
                    dataKey="date"
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                    domain={[0, 100]}
                    tickFormatter={(v: number) => `${v}%`}
                    width={45}
                  />
                  <Tooltip
                    formatter={(value) => [formatOccupancy(Number(value)), "Occupancy"]}
                    contentStyle={{ fontSize: 12 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          {hasNoi && (
            <div className="border border-zinc-200 rounded-md p-4">
              <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-3">
                NOI Trend
              </h4>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={noiData}>
                  <XAxis
                    dataKey="date"
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={tickStyle}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v: number) => formatNoi(v)}
                    width={55}
                  />
                  <Tooltip
                    formatter={(value) => [formatNoi(Number(value)), "NOI"]}
                    contentStyle={{ fontSize: 12 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {hasDscr && (
        <div className="border border-zinc-200 rounded-md p-4">
          <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-3">
            DSCR (NOI) Trend
          </h4>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={dscrData}>
              <XAxis
                dataKey="date"
                tick={tickStyle}
                axisLine={false}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={tickStyle}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${v.toFixed(1)}x`}
                width={45}
              />
              <Tooltip
                formatter={(value) => [formatDscr(Number(value)), "DSCR"]}
                contentStyle={{ fontSize: 12 }}
              />
              <ReferenceLine
                y={1.25}
                stroke="#d4d4d8"
                strokeDasharray="4 4"
                label={{
                  value: "1.25x",
                  position: "right",
                  fill: "#a1a1aa",
                  fontSize: 10,
                }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
