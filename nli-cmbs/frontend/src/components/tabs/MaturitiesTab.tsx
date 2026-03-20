import { useMemo } from "react";
import { MetricCard } from "@/components/MetricCard";
import { PropertyTypeBadge, MonthsBadge, StatusBadge } from "@/components/StatusBadge";
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
  loanDisplayName,
  monthsUntil,
  isMaturityDefault,
} from "@/lib/format";

interface MaturitiesTabProps {
  loans: Loan[];
}

/** Returns true if delinquency status indicates defeased */
function isDefeased(loan: Loan): boolean {
  const status = loan.latest_snapshot?.delinquency_status ?? "";
  return /defeas/i.test(status);
}

/** Returns true if loan is paid off or defeased */
function isPaidOffOrDefeased(loan: Loan): boolean {
  const bal = loanBalance(loan);
  const endingBal = loan.latest_snapshot?.ending_balance;
  return bal === 0 || endingBal === 0 || (endingBal == null && loan.latest_snapshot != null) || isDefeased(loan);
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

  // --- Maturity Default: past maturity date with balance > 0 (date-based, not status-based) ---
  const maturityDefault = useMemo(() => {
    return activeLoans
      .filter((l) => {
        if (isPaidOffOrDefeased(l)) return false;
        return isMaturityDefault(l);
      })
      .sort((a, b) => loanBalance(b) - loanBalance(a));
  }, [activeLoans]);

  // Set of maturity default loan IDs for exclusion from maturing24
  const maturityDefaultIds = useMemo(
    () => new Set(maturityDefault.map((l) => l.id)),
    [maturityDefault]
  );

  // --- Maturing loans: future maturity (or within 30 day grace), balance > 0, not defeased, not maturity default ---
  const maturing24 = useMemo(() => {
    return activeLoans
      .filter((l) => {
        if (isPaidOffOrDefeased(l)) return false;
        if (loanBalance(l) <= 0) return false;
        if (maturityDefaultIds.has(l.id)) return false;
        const m = monthsUntil(l.maturity_date);
        if (m == null) return false;
        // future or within ~30 day grace period (m >= -1)
        return m >= -1 && m <= 24;
      })
      .sort((a, b) => {
        const ad = a.maturity_date ?? "";
        const bd = b.maturity_date ?? "";
        return ad.localeCompare(bd);
      });
  }, [activeLoans, maturityDefaultIds]);

  // --- Paid Off / Defeased ---
  const paidOff = useMemo(() => {
    return activeLoans
      .filter((l) => isPaidOffOrDefeased(l))
      .sort((a, b) => {
        const ad = a.maturity_date ?? "";
        const bd = b.maturity_date ?? "";
        return bd.localeCompare(ad); // descending
      });
  }, [activeLoans]);

  // Metric card filters: only future maturities with balance > 0
  const mat012 = useMemo(() => {
    return maturing24.filter((l) => {
      const m = monthsUntil(l.maturity_date);
      return m != null && m >= 0 && m <= 12;
    });
  }, [maturing24]);

  const mat1324 = useMemo(() => {
    return maturing24.filter((l) => {
      const m = monthsUntil(l.maturity_date);
      return m != null && m >= 13 && m <= 24;
    });
  }, [maturing24]);

  const mat012Balance = mat012.reduce((sum, l) => sum + loanBalance(l), 0);
  const mat1324Balance = mat1324.reduce((sum, l) => sum + loanBalance(l), 0);

  // WA in-place rate (only actionable maturing loans)
  const waRate = useMemo(() => {
    let totalWeightedRate = 0;
    let totalBal = 0;
    for (const loan of maturing24) {
      const rate =
        loan.latest_snapshot?.current_interest_rate ??
        loan.original_interest_rate;
      if (rate == null) continue;
      const bal = loanBalance(loan);
      totalWeightedRate += rate * bal;
      totalBal += bal;
    }
    return totalBal > 0 ? totalWeightedRate / totalBal : null;
  }, [maturing24]);

  // IO count for maturing loans
  const fixedCount = maturing24.filter(
    (l) => !l.interest_only_indicator
  ).length;
  const ioCount = maturing24.filter(
    (l) => l.interest_only_indicator
  ).length;

  // DSCR < 1.25x maturing (only actionable future maturities)
  const lowDscrMaturing = useMemo(() => {
    return maturing24.filter((l) => {
      const dscr =
        l.latest_snapshot?.dscr_noi ??
        l.latest_snapshot?.dscr_noi_at_securitization;
      return dscr != null && dscr < 1.25;
    });
  }, [maturing24]);

  const lowDscrBalance = lowDscrMaturing.reduce(
    (sum, l) => sum + loanBalance(l),
    0
  );

  // Maturity Default metrics
  const matDefaultBalance = maturityDefault.reduce(
    (sum, l) => sum + loanBalance(l),
    0
  );
  const avgMonthsPastMaturity = useMemo(() => {
    if (maturityDefault.length === 0) return 0;
    const total = maturityDefault.reduce((sum, l) => {
      const m = monthsUntil(l.maturity_date);
      return sum + Math.abs(m ?? 0);
    }, 0);
    return Math.round(total / maturityDefault.length);
  }, [maturityDefault]);

  // Loans with balance > 0 for chart (exclude paid off and maturity defaults)
  const loansWithBalance = useMemo(
    () => activeLoans.filter((l) => loanBalance(l) > 0 && !isPaidOffOrDefeased(l) && !maturityDefaultIds.has(l.id)),
    [activeLoans, maturityDefaultIds]
  );

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
        <MaturityWallChart loans={loansWithBalance} maturityDefault={maturityDefault} />
      </div>

      {/* Maturing loans table */}
      {maturing24.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-zinc-700 mb-1">
            Maturing Loans (Next 24 Months)
          </h3>
          <p className="text-xs text-zinc-400 italic mb-2">
            Active loans approaching maturity sorted by nearest date
          </p>
          <div className="border border-zinc-200 rounded-md overflow-auto max-h-[500px]">
            <Table>
              <TableHeader className="bg-zinc-50 sticky top-0 z-10">
                <TableRow className="hover:bg-zinc-50">
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Loan ID
                  </TableHead>
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
                      <TableCell className="py-1.5 font-mono text-xs text-zinc-500">
                        {loan.prospectus_loan_id}
                      </TableCell>
                      <TableCell className="py-1.5 font-medium text-sm max-w-[180px] truncate">
                        {loanDisplayName(loan)}
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
        </div>
      )}

      {/* Maturity Default section */}
      {maturityDefault.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-zinc-700 mb-1">
            Maturity Default
          </h3>
          <p className="text-xs text-zinc-400 italic mb-2">
            Loans past maturity date that have not been refinanced or paid off — balloon payment in default
          </p>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-2">
            <MetricCard
              label="Maturity Default"
              value={`${maturityDefault.length} loans`}
              sub={fmtBalance(matDefaultBalance)}
              color="text-rose-600"
            />
            <MetricCard
              label="Total Default Balance"
              value={fmtBalance(matDefaultBalance)}
              sub={pctOf(matDefaultBalance) + " of pool"}
              color="text-rose-600"
            />
            <MetricCard
              label="Avg Months Past Maturity"
              value={`${avgMonthsPastMaturity}mo`}
              color="text-amber-600"
            />
          </div>

          <div className="border border-zinc-200 rounded-md overflow-auto max-h-[500px]">
            <Table>
              <TableHeader className="bg-zinc-50 sticky top-0 z-10">
                <TableRow className="hover:bg-zinc-50">
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Loan ID
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Property
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Type
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Balance
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
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Status
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {maturityDefault.map((loan, i) => {
                  const rate =
                    loan.latest_snapshot?.current_interest_rate ??
                    loan.original_interest_rate;
                  const dscr =
                    loan.latest_snapshot?.dscr_noi ??
                    loan.latest_snapshot?.dscr_noi_at_securitization;

                  return (
                    <TableRow
                      key={loan.id ?? i}
                      className={`text-sm ${i % 2 === 0 ? "bg-white" : "bg-zinc-50/50"}`}
                    >
                      <TableCell className="py-1.5 font-mono text-xs text-zinc-500">
                        {loan.prospectus_loan_id}
                      </TableCell>
                      <TableCell className="py-1.5 font-medium text-sm max-w-[180px] truncate">
                        {loanDisplayName(loan)}
                      </TableCell>
                      <TableCell className="py-1.5">
                        <PropertyTypeBadge code={loan.property_type} />
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        {fmtBalance(loanBalance(loan))}
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        {fmtRate(rate)}
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        <span
                          className={
                            dscr != null && dscr < 1.25 ? "text-rose-600" : ""
                          }
                        >
                          {fmtDscr(dscr)}
                        </span>
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        {fmtMonthYear(loan.maturity_date)}
                      </TableCell>
                      <TableCell className="py-1.5">
                        <StatusBadge
                          status={loan.latest_snapshot?.delinquency_status}
                        />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      )}

      {/* Paid Off / Defeased section — always open, hidden if 0 loans */}
      {paidOff.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-zinc-700 mb-1">
            Paid Off / Defeased ({paidOff.length} loans)
          </h3>
          <p className="text-xs text-zinc-400 italic mb-2">
            Loans that have been retired from the pool
          </p>

          <div className="border border-zinc-200 rounded-md overflow-auto max-h-[400px]">
            <Table>
              <TableHeader className="bg-zinc-50 sticky top-0 z-10">
                <TableRow className="hover:bg-zinc-50">
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Loan ID
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Property
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Type
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Original Balance
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Status
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Maturity
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paidOff.map((loan, i) => (
                  <TableRow
                    key={loan.id ?? i}
                    className={`text-sm ${i % 2 === 0 ? "bg-white" : "bg-zinc-50/50"}`}
                  >
                    <TableCell className="py-1.5 font-mono text-xs text-zinc-500">
                      {loan.prospectus_loan_id}
                    </TableCell>
                    <TableCell className="py-1.5 font-medium text-sm max-w-[180px] truncate">
                      {loanDisplayName(loan)}
                    </TableCell>
                    <TableCell className="py-1.5">
                      <PropertyTypeBadge code={loan.property_type} />
                    </TableCell>
                    <TableCell className="py-1.5 text-right font-mono text-sm">
                      {fmtBalance(loan.original_loan_amount)}
                    </TableCell>
                    <TableCell className="py-1.5">
                      {isDefeased(loan) ? (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-zinc-100 text-zinc-600">
                          Defeased
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-zinc-100 text-zinc-600">
                          Paid Off
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="py-1.5 text-right font-mono text-sm">
                      {fmtMonthYear(loan.maturity_date)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}
    </div>
  );
}
