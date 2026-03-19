import { useMemo } from "react";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge, PropertyTypeBadge } from "@/components/StatusBadge";
import { ReportPanel } from "@/components/report/ReportPanel";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { DealDetail, Loan } from "@/lib/types";
import { fmtBalance, fmtPct, fmtDscr, loanBalance, getDelinquencyInfo, isMaturedBalloon } from "@/lib/format";

interface OverviewTabProps {
  deal: DealDetail;
  loans: Loan[];
  ticker: string;
}

export function OverviewTab({ deal, loans, ticker }: OverviewTabProps) {
  const top10 = useMemo(() => {
    return [...loans]
      .sort((a, b) => loanBalance(b) - loanBalance(a))
      .slice(0, 10);
  }, [loans]);

  const totalBalance = useMemo(
    () => loans.reduce((sum, l) => sum + loanBalance(l), 0),
    [loans]
  );

  const defeased = useMemo(
    () =>
      loans.filter((l) => {
        const s = (l.latest_snapshot?.delinquency_status ?? "").toLowerCase();
        return s.includes("defeas");
      }).length,
    [loans]
  );

  // Compute SS pct by balance using canonical delinquency codes
  const { ssBalance, ssCount } = useMemo(() => {
    const ss = loans.filter((l) =>
      getDelinquencyInfo(l.latest_snapshot?.delinquency_status).isSpeciallyServiced
    );
    return {
      ssBalance: ss.reduce((sum, l) => sum + loanBalance(l), 0),
      ssCount: ss.length,
    };
  }, [loans]);
  const ssPct = totalBalance > 0 ? (ssBalance / totalBalance) * 100 : 0;

  // Delinquency by balance — excludes performing matured balloons ("B"),
  // which are maturity risk not payment delinquency
  const { dqBalance, dqCount } = useMemo(() => {
    const dq = loans.filter((l) => {
      const status = l.latest_snapshot?.delinquency_status;
      const info = getDelinquencyInfo(status);
      return info.isDelinquent && !((status ?? "").trim() === "B");
    });
    return {
      dqBalance: dq.reduce((sum, l) => sum + loanBalance(l), 0),
      dqCount: dq.length,
    };
  }, [loans]);
  const dqPctBalance = totalBalance > 0 ? (dqBalance / totalBalance) * 100 : 0;

  // Matured balloon loans (codes "A" and "B")
  const { maturedBalance, maturedCount } = useMemo(() => {
    const mat = loans.filter((l) =>
      isMaturedBalloon(l.latest_snapshot?.delinquency_status)
    );
    return {
      maturedBalance: mat.reduce((sum, l) => sum + loanBalance(l), 0),
      maturedCount: mat.length,
    };
  }, [loans]);
  const maturedPct = totalBalance > 0 ? (maturedBalance / totalBalance) * 100 : 0;

  // IO loans
  const ioLoans = loans.filter((l) => l.interest_only_indicator);
  const ioBalance = ioLoans.reduce((sum, l) => sum + loanBalance(l), 0);
  const ioPct = totalBalance > 0 ? (ioBalance / totalBalance) * 100 : 0;

  // Use client-side DQ rate which correctly excludes performing matured balloons ("B").
  // The API's deal.delinquency_rate may include "B" loans, so we prefer our calculation.
  const dqColor = dqPctBalance > 5 ? "text-rose-600" : undefined;
  const ssColor = ssPct > 5 ? "text-rose-600" : undefined;
  const dscrColor = (deal.wa_dscr ?? 0) < 1.25 ? "text-rose-600" : undefined;

  return (
    <div className="space-y-4">
      {/* Row 1: 4 metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <MetricCard
          label="Current UPB"
          value={deal.total_upb ? fmtBalance(deal.total_upb) : "\u2014"}
          sub={deal.original_balance ? `Orig: ${fmtBalance(deal.original_balance)}` : undefined}
        />
        <MetricCard
          label="Loan Count"
          value={deal.loan_count?.toLocaleString() ?? "\u2014"}
          sub={defeased > 0 ? `${defeased} defeased` : undefined}
        />
        <MetricCard
          label="WA Coupon"
          value={deal.wa_coupon != null ? `${deal.wa_coupon.toFixed(2)}%` : "\u2014"}
        />
        <MetricCard
          label="WA DSCR"
          value={deal.wa_dscr != null ? fmtDscr(deal.wa_dscr) : "\u2014"}
          color={dscrColor}
        />
      </div>

      {/* Row 2: metric cards */}
      <div className={`grid grid-cols-2 ${maturedCount > 0 ? "md:grid-cols-5" : "md:grid-cols-4"} gap-2`}>
        <MetricCard
          label="Delinquency Rate"
          value={fmtPct(dqPctBalance)}
          sub={`${dqCount} loans by count`}
          color={dqColor}
        />
        <MetricCard
          label="Specially Serviced"
          value={fmtPct(ssPct)}
          sub={`${ssCount} loans`}
          color={ssColor}
        />
        <MetricCard
          label="WA LTV"
          value={deal.wa_ltv != null ? fmtPct(deal.wa_ltv) : "\u2014"}
        />
        <MetricCard
          label="IO Loans"
          value={fmtPct(deal.pct_interest_only ?? ioPct)}
          sub={`${ioLoans.length} loans`}
        />
        {maturedCount > 0 && (
          <MetricCard
            label="Matured Loans"
            value={fmtPct(maturedPct)}
            sub={`${maturedCount} loans \u00B7 ${fmtBalance(maturedBalance)}`}
            color="text-amber-600"
          />
        )}
      </div>

      {/* Top 10 loans table */}
      <div>
        <h3 className="text-sm font-semibold text-zinc-700 mb-2">
          Top 10 Loans
        </h3>
        <div className="border border-zinc-200 rounded-md overflow-auto">
          <Table>
            <TableHeader className="bg-zinc-50">
              <TableRow className="hover:bg-zinc-50">
                <TableHead className="text-[11px] uppercase font-medium text-zinc-500">Property</TableHead>
                <TableHead className="text-[11px] uppercase font-medium text-zinc-500">Type</TableHead>
                <TableHead className="text-[11px] uppercase font-medium text-zinc-500">Location</TableHead>
                <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">Balance</TableHead>
                <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">% Pool</TableHead>
                <TableHead className="text-[11px] uppercase font-medium text-zinc-500">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {top10.map((loan, i) => {
                const bal = loanBalance(loan);
                const pctPool = totalBalance > 0 ? (bal / totalBalance) * 100 : 0;
                const propName =
                  loan.property_count > 1
                    ? `${loan.property_name ?? "Portfolio"} (${loan.property_count})`
                    : loan.property_name ?? "\u2014";
                const location = [loan.property_city, loan.property_state]
                  .filter(Boolean)
                  .join(", ");

                return (
                  <TableRow
                    key={loan.id ?? i}
                    className={`text-sm ${i % 2 === 0 ? "bg-white" : "bg-zinc-50/50"}`}
                  >
                    <TableCell className="py-1.5 font-medium text-sm max-w-[200px] truncate">
                      {propName}
                    </TableCell>
                    <TableCell className="py-1.5">
                      <PropertyTypeBadge code={loan.property_type} />
                    </TableCell>
                    <TableCell className="py-1.5 text-sm text-zinc-600">
                      {location || "\u2014"}
                    </TableCell>
                    <TableCell className="py-1.5 text-right font-mono text-sm">
                      {fmtBalance(bal)}
                    </TableCell>
                    <TableCell className="py-1.5 text-right font-mono text-sm">
                      {pctPool.toFixed(1)}%
                    </TableCell>
                    <TableCell className="py-1.5">
                      <StatusBadge status={loan.latest_snapshot?.delinquency_status} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* AI Report */}
      <ReportPanel ticker={ticker} />
    </div>
  );
}
