import { useMemo } from "react";
import { MetricCard } from "@/components/MetricCard";
import { PropertyTypeBadge, MonthsBadge } from "@/components/StatusBadge";
import { MaturityWallChart } from "@/components/charts/MaturityWallChart";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Loan } from "@/lib/types";
import {
  fmtBalance,
  fmtRate,
  fmtDscr,
  fmtMonthYear,
  loanBalance,
  monthsUntil,
} from "@/lib/format";

interface MaturitiesTabProps {
  loans: Loan[];
}

export function MaturitiesTab({ loans }: MaturitiesTabProps) {
  const totalBalance = useMemo(
    () => loans.reduce((sum, l) => sum + loanBalance(l), 0),
    [loans]
  );

  // Active loans (not child notes)
  const activeLoans = useMemo(
    () => loans.filter((l) => !l.parent_loan_id),
    [loans]
  );

  // Maturing 0-12 months
  const mat012 = useMemo(() => {
    return activeLoans.filter((l) => {
      const m = monthsUntil(l.maturity_date);
      return m != null && m >= 0 && m <= 12;
    });
  }, [activeLoans]);

  // Maturing 13-24 months
  const mat1324 = useMemo(() => {
    return activeLoans.filter((l) => {
      const m = monthsUntil(l.maturity_date);
      return m != null && m >= 13 && m <= 24;
    });
  }, [activeLoans]);

  const mat012Balance = mat012.reduce((sum, l) => sum + loanBalance(l), 0);
  const mat1324Balance = mat1324.reduce((sum, l) => sum + loanBalance(l), 0);

  // WA in-place rate
  const waRate = useMemo(() => {
    let totalWeightedRate = 0;
    let totalBal = 0;
    for (const loan of activeLoans) {
      const rate =
        loan.latest_snapshot?.current_interest_rate ??
        loan.original_interest_rate;
      if (rate == null) continue;
      const bal = loanBalance(loan);
      totalWeightedRate += rate * bal;
      totalBal += bal;
    }
    return totalBal > 0 ? totalWeightedRate / totalBal : null;
  }, [activeLoans]);

  // IO count
  const fixedCount = activeLoans.filter(
    (l) => !l.interest_only_indicator
  ).length;
  const ioCount = activeLoans.filter(
    (l) => l.interest_only_indicator
  ).length;

  // DSCR < 1.25x maturing (0-24 months)
  const lowDscrMaturing = useMemo(() => {
    return activeLoans.filter((l) => {
      const m = monthsUntil(l.maturity_date);
      if (m == null || m < 0 || m > 24) return false;
      const dscr =
        l.latest_snapshot?.dscr_noi ??
        l.latest_snapshot?.dscr_noi_at_securitization;
      return dscr != null && dscr < 1.25;
    });
  }, [activeLoans]);

  const lowDscrBalance = lowDscrMaturing.reduce(
    (sum, l) => sum + loanBalance(l),
    0
  );

  // Maturing loans next 24 months, sorted by maturity date
  const maturing24 = useMemo(() => {
    return activeLoans
      .filter((l) => {
        const m = monthsUntil(l.maturity_date);
        return m != null && m <= 24;
      })
      .sort((a, b) => {
        const ad = a.maturity_date ?? "";
        const bd = b.maturity_date ?? "";
        return ad.localeCompare(bd);
      });
  }, [activeLoans]);

  const pctOf = (bal: number) =>
    totalBalance > 0 ? ((bal / totalBalance) * 100).toFixed(1) + "%" : "\u2014";

  return (
    <div className="space-y-4">
      {/* Metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <MetricCard
          label="Maturing 0-12mo"
          value={fmtBalance(mat012Balance)}
          sub={`${mat012.length} loans \u00B7 ${pctOf(mat012Balance)}`}
        />
        <MetricCard
          label="Maturing 13-24mo"
          value={fmtBalance(mat1324Balance)}
          sub={`${mat1324.length} loans \u00B7 ${pctOf(mat1324Balance)}`}
        />
        <MetricCard
          label="WA In-Place Rate"
          value={waRate != null ? fmtRate(waRate) : "\u2014"}
          sub={`Fixed: ${fixedCount} \u00B7 IO: ${ioCount}`}
        />
        <MetricCard
          label="DSCR < 1.25x Maturing"
          value={`${lowDscrMaturing.length} loans`}
          sub={fmtBalance(lowDscrBalance)}
          color="text-amber-600"
        />
      </div>

      {/* Maturity wall chart */}
      <div className="border border-zinc-200 rounded-md p-4">
        <MaturityWallChart loans={activeLoans} />
      </div>

      {/* Maturing loans table */}
      <div>
        <h3 className="text-sm font-semibold text-zinc-700 mb-1">
          Maturing Loans (Next 24 Months)
        </h3>
        <p className="text-xs text-zinc-400 italic mb-2">
          Sorted by maturity date
        </p>
        {maturing24.length === 0 ? (
          <div className="border border-zinc-200 rounded-md p-4 text-center text-sm text-zinc-400">
            No loans maturing in the next 24 months
          </div>
        ) : (
          <div className="border border-zinc-200 rounded-md overflow-auto max-h-[500px]">
            <Table>
              <TableHeader className="bg-zinc-50 sticky top-0 z-10">
                <TableRow className="hover:bg-zinc-50">
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Property
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Type
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Balance
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Rate Type
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Rate
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    DSCR
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Maturity
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Months
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {maturing24.map((loan, i) => {
                  const months = monthsUntil(loan.maturity_date);
                  const rate =
                    loan.latest_snapshot?.current_interest_rate ??
                    loan.original_interest_rate;
                  const currentDscr = loan.latest_snapshot?.dscr_noi ?? null;
                  const dscr = currentDscr ?? loan.latest_snapshot?.dscr_noi_at_securitization ?? null;
                  const dscrIsSecuritization = currentDscr == null && dscr != null;
                  const isIO = loan.interest_only_indicator;

                  return (
                    <TableRow
                      key={loan.id ?? i}
                      className={`text-sm ${i % 2 === 0 ? "bg-white" : "bg-zinc-50/50"}`}
                    >
                      <TableCell className="py-1.5 font-medium text-sm max-w-[180px] truncate">
                        {loan.property_name ?? "\u2014"}
                      </TableCell>
                      <TableCell className="py-1.5">
                        <PropertyTypeBadge code={loan.property_type} />
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        {fmtBalance(loanBalance(loan))}
                      </TableCell>
                      <TableCell className="py-1.5">
                        <span className="inline-flex items-center gap-1">
                          {isIO && (
                            <span className="text-[11px] px-1 py-0.5 rounded bg-blue-50 text-blue-700">
                              IO
                            </span>
                          )}
                        </span>
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        {fmtRate(rate)}
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        <span
                          className={
                            dscr != null && dscr < 1.25
                              ? "text-rose-600"
                              : dscrIsSecuritization ? "text-zinc-400" : ""
                          }
                          title={dscrIsSecuritization ? "At securitization" : undefined}
                        >
                          {fmtDscr(dscr)}
                          {dscrIsSecuritization && <sup className="text-[9px] ml-0.5">s</sup>}
                        </span>
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        {fmtMonthYear(loan.maturity_date)}
                      </TableCell>
                      <TableCell className="py-1.5 text-right">
                        <MonthsBadge months={months} />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}
