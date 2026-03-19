import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { PropertySnapshot } from "@/lib/types";
import { fmtBalance, fmtDscr } from "@/lib/format";

function fmtPeriod(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function fmtOcc(value: number | null): string {
  if (value == null) return "\u2014";
  const pct = value <= 1 ? value * 100 : value;
  return `${pct.toFixed(1)}%`;
}

interface PropertyHistoryTableProps {
  snapshots: PropertySnapshot[];
}

export function PropertyHistoryTable({ snapshots }: PropertyHistoryTableProps) {
  const sorted = [...snapshots].sort((a, b) =>
    b.reporting_period_end.localeCompare(a.reporting_period_end)
  );

  return (
    <div className="border border-zinc-200 rounded-md overflow-auto max-h-[400px]">
      <Table>
        <TableHeader className="bg-zinc-50 sticky top-0 z-10">
          <TableRow className="hover:bg-zinc-50">
            <TableHead className="text-[11px] uppercase font-medium text-zinc-500">Period</TableHead>
            <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">Occupancy</TableHead>
            <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">NOI</TableHead>
            <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">NCF</TableHead>
            <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">DSCR (NOI)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((s, i) => (
            <TableRow
              key={s.reporting_period_end}
              className={`text-sm ${i % 2 === 0 ? "bg-white" : "bg-zinc-50/50"}`}
            >
              <TableCell className="py-1.5 font-medium">{fmtPeriod(s.reporting_period_end)}</TableCell>
              <TableCell className="py-1.5 text-right font-mono">{fmtOcc(s.occupancy)}</TableCell>
              <TableCell className="py-1.5 text-right font-mono">{fmtBalance(s.noi)}</TableCell>
              <TableCell className="py-1.5 text-right font-mono">{fmtBalance(s.ncf)}</TableCell>
              <TableCell className="py-1.5 text-right font-mono">
                <span className={s.dscr_noi != null && s.dscr_noi < 1.25 ? "text-rose-600" : ""}>
                  {fmtDscr(s.dscr_noi)}
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
