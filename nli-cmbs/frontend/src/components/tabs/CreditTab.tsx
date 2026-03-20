import { useMemo, useState } from "react";
import { MetricCard } from "@/components/MetricCard";
import { StatusBadge, PropertyTypeBadge } from "@/components/StatusBadge";
import { DelinquencyLineChart } from "@/components/charts/DelinquencyLineChart";
import type { DelinquencyTrendPoint } from "@/components/charts/DelinquencyLineChart";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Loan } from "@/lib/types";
import { fmtBalance, fmtDscr, fmtRate, fmtMonthYear, loanBalance, loanDisplayName, getDelinquencyInfo, isMaturityDefault } from "@/lib/format";

interface CreditTabProps {
  loans: Loan[];
}

export function CreditTab({ loans }: CreditTabProps) {
  const [expandedSS, setExpandedSS] = useState<Set<string>>(new Set());

  const totalBalance = useMemo(
    () => loans.reduce((sum, l) => sum + loanBalance(l), 0),
    [loans]
  );

  // Bucket counts and balances using canonical delinquency codes
  // B (performing balloon) → current bucket; A (non-performing) → 90+ bucket
  const buckets = useMemo(() => {
    const b = {
      current: { count: 0, balance: 0 },
      "30": { count: 0, balance: 0 },
      "60": { count: 0, balance: 0 },
      "90+": { count: 0, balance: 0 },
    };
    for (const loan of loans) {
      if (loan.parent_loan_id) continue;
      const info = getDelinquencyInfo(loan.latest_snapshot?.delinquency_status);
      const bal = loanBalance(loan);
      if (info.severity >= 3) {
        b["90+"].count++;
        b["90+"].balance += bal;
      } else if (info.severity === 2) {
        b["60"].count++;
        b["60"].balance += bal;
      } else if (info.severity === 1) {
        b["30"].count++;
        b["30"].balance += bal;
      } else {
        b.current.count++;
        b.current.balance += bal;
      }
    }
    return b;
  }, [loans]);

  const pctOf = (bal: number) =>
    totalBalance > 0 ? ((bal / totalBalance) * 100).toFixed(2) + "%" : "\u2014";

  // Delinquent loans (30+ days)
  const delinquentLoans = useMemo(
    () =>
      loans.filter(
        (l) =>
          !l.parent_loan_id &&
          getDelinquencyInfo(l.latest_snapshot?.delinquency_status).isDelinquent
      ),
    [loans]
  );

  // Specially serviced loans
  const ssLoans = useMemo(
    () =>
      loans.filter(
        (l) =>
          !l.parent_loan_id &&
          getDelinquencyInfo(l.latest_snapshot?.delinquency_status).isSpeciallyServiced
      ),
    [loans]
  );

  const ssBalance = ssLoans.reduce((sum, l) => sum + loanBalance(l), 0);

  // Maturity default loans (past maturity date with balance > 0)
  const maturedLoans = useMemo(
    () =>
      loans.filter(
        (l) =>
          !l.parent_loan_id &&
          isMaturityDefault(l)
      ),
    [loans]
  );
  const maturedBalance = maturedLoans.reduce((sum, l) => sum + loanBalance(l), 0);

  // Modified performing loans (is_modified field may not exist on current type)
  const modifiedLoans: Loan[] = [];

  // Trend data - we don't have historical data, so pass empty
  const trendData: DelinquencyTrendPoint[] = [];

  const toggleExpand = (id: string) => {
    setExpandedSS((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-4">
      {/* Delinquency buckets */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <MetricCard
          label="Current"
          value={pctOf(buckets.current.balance)}
          sub={`${fmtBalance(buckets.current.balance)} \u00B7 ${buckets.current.count} loans`}
          color="text-emerald-600"
        />
        <MetricCard
          label="30-59 Days"
          value={pctOf(buckets["30"].balance)}
          sub={`${fmtBalance(buckets["30"].balance)} \u00B7 ${buckets["30"].count} loans`}
        />
        <MetricCard
          label="60-89 Days"
          value={pctOf(buckets["60"].balance)}
          sub={`${fmtBalance(buckets["60"].balance)} \u00B7 ${buckets["60"].count} loans`}
          color="text-amber-600"
        />
        <MetricCard
          label="90+ Days"
          value={pctOf(buckets["90+"].balance)}
          sub={`${fmtBalance(buckets["90+"].balance)} \u00B7 ${buckets["90+"].count} loans`}
          color="text-rose-600"
        />
      </div>

      {/* TODO: Wire to historical loan snapshots API */}
      {trendData.length > 0 && (
        <div className="border border-zinc-200 rounded-md p-4">
          <DelinquencyLineChart data={trendData} />
        </div>
      )}

      {/* Delinquent loans */}
      <div>
        <h3 className="text-sm font-semibold text-zinc-700 mb-1">
          Delinquent Loans
        </h3>
        <p className="text-xs text-zinc-400 italic mb-2">
          Loans 30+ days past due on scheduled payments
        </p>
        {delinquentLoans.length === 0 ? (
          <div className="border border-zinc-200 rounded-md p-4 text-center text-sm text-zinc-400">
            No delinquent loans
          </div>
        ) : (
          <div className="border border-zinc-200 rounded-md overflow-auto">
            <Table>
              <TableHeader className="bg-zinc-50">
                <TableRow className="hover:bg-zinc-50">
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Loan ID
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Property
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Balance
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Status
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Days DQ
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    DSCR
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    In SS?
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {delinquentLoans.map((loan, i) => {
                  const location = [loan.property_city, loan.property_state]
                    .filter(Boolean)
                    .join(", ");
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
                      <TableCell className="py-1.5">
                        <div className="font-medium text-sm">
                          {loanDisplayName(loan)}
                        </div>
                        <div className="text-[11px] text-zinc-400">
                          {location}
                          {loan.property_type && (
                            <>
                              {" \u00B7 "}
                              <PropertyTypeBadge code={loan.property_type} />
                            </>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        {fmtBalance(loanBalance(loan))}
                      </TableCell>
                      <TableCell className="py-1.5">
                        <StatusBadge
                          status={loan.latest_snapshot?.delinquency_status}
                        />
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        {(() => {
                          const info = getDelinquencyInfo(loan.latest_snapshot?.delinquency_status);
                          return info.label;
                        })()}
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        <span
                          className={
                            dscr != null && dscr < 1.25
                              ? "text-rose-600"
                              : ""
                          }
                        >
                          {fmtDscr(dscr)}
                        </span>
                      </TableCell>
                      <TableCell className="py-1.5 text-sm">
                        {getDelinquencyInfo(loan.latest_snapshot?.delinquency_status).isSpeciallyServiced
                          ? "Yes"
                          : "No"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Matured loans */}
      <div>
        <h3 className="text-sm font-semibold text-zinc-700 mb-1">
          Maturity Default
        </h3>
        <p className="text-xs text-zinc-400 italic mb-2">
          Loans past maturity date that have not been refinanced or paid off
        </p>

        {maturedLoans.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2">
            <MetricCard
              label="Maturity Default"
              value={maturedLoans.length.toString()}
              color="text-rose-600"
            />
            <MetricCard
              label="Default Balance"
              value={fmtBalance(maturedBalance)}
              sub={pctOf(maturedBalance) + " of pool"}
              color="text-rose-600"
            />
          </div>
        )}

        {maturedLoans.length === 0 ? (
          <div className="border border-zinc-200 rounded-md p-4 text-center text-sm text-zinc-400">
            No matured loans
          </div>
        ) : (
          <div className="border border-zinc-200 rounded-md overflow-auto">
            <Table>
              <TableHeader className="bg-zinc-50">
                <TableRow className="hover:bg-zinc-50">
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Loan ID
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Property
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Balance
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Status
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Maturity
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Rate
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    DSCR
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {maturedLoans.map((loan, i) => {
                  const location = [loan.property_city, loan.property_state]
                    .filter(Boolean)
                    .join(", ");
                  const dscr =
                    loan.latest_snapshot?.dscr_noi ??
                    loan.latest_snapshot?.dscr_noi_at_securitization;
                  const rate =
                    loan.latest_snapshot?.current_interest_rate ??
                    loan.original_interest_rate;
                  return (
                    <TableRow
                      key={loan.id ?? i}
                      className={`text-sm ${i % 2 === 0 ? "bg-white" : "bg-zinc-50/50"}`}
                    >
                      <TableCell className="py-1.5 font-mono text-xs text-zinc-500">
                        {loan.prospectus_loan_id}
                      </TableCell>
                      <TableCell className="py-1.5">
                        <div className="font-medium text-sm">
                          {loanDisplayName(loan)}
                        </div>
                        <div className="text-[11px] text-zinc-400">
                          {location}
                          {loan.property_type && (
                            <>
                              {" \u00B7 "}
                              <PropertyTypeBadge code={loan.property_type} />
                            </>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        {fmtBalance(loanBalance(loan))}
                      </TableCell>
                      <TableCell className="py-1.5">
                        <StatusBadge
                          status={loan.latest_snapshot?.delinquency_status}
                        />
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        {fmtMonthYear(loan.maturity_date)}
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        {fmtRate(rate)}
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-sm">
                        <span
                          className={
                            dscr != null && dscr < 1.25
                              ? "text-rose-600"
                              : ""
                          }
                        >
                          {fmtDscr(dscr)}
                        </span>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Specially serviced loans */}
      <div>
        <h3 className="text-sm font-semibold text-zinc-700 mb-1">
          Specially Serviced Loans
        </h3>
        <p className="text-xs text-zinc-400 italic mb-2">
          Loans transferred to special servicer for workout due to default,
          imminent default, or maturity default
        </p>

        {ssLoans.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2">
            <MetricCard
              label="SS Loans"
              value={ssLoans.length.toString()}
            />
            <MetricCard
              label="SS Balance"
              value={fmtBalance(ssBalance)}
              sub={pctOf(ssBalance) + " of pool"}
            />
          </div>
        )}

        {ssLoans.length === 0 ? (
          <div className="border border-zinc-200 rounded-md p-4 text-center text-sm text-zinc-400">
            No specially serviced loans
          </div>
        ) : (
          <div className="border border-zinc-200 rounded-md overflow-auto">
            <Table>
              <TableHeader className="bg-zinc-50">
                <TableRow className="hover:bg-zinc-50">
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Loan ID
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Property
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500 text-right">
                    Balance
                  </TableHead>
                  <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                    Status
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ssLoans.map((loan, i) => (
                  <>
                    <TableRow
                      key={loan.id ?? i}
                      className={`text-sm cursor-pointer ${i % 2 === 0 ? "bg-white" : "bg-zinc-50/50"}`}
                      onClick={() => toggleExpand(loan.id)}
                    >
                      <TableCell className="py-1.5 font-mono text-xs text-zinc-500">
                        {loan.prospectus_loan_id}
                      </TableCell>
                      <TableCell className="py-1.5 font-medium">
                        {loanDisplayName(loan)}
                      </TableCell>
                      <TableCell className="py-1.5 text-right font-mono">
                        {fmtBalance(loanBalance(loan))}
                      </TableCell>
                      <TableCell className="py-1.5">
                        <StatusBadge
                          status={loan.latest_snapshot?.delinquency_status}
                        />
                      </TableCell>
                    </TableRow>
                    {expandedSS.has(loan.id) && (
                      <TableRow key={`${loan.id}-detail`} className="bg-zinc-50">
                        <TableCell colSpan={4} className="py-2 px-4">
                          <div className="text-xs text-zinc-500 space-y-1">
                            <div>
                              Loan ID: {loan.prospectus_loan_id} | Origination:{" "}
                              {loan.origination_date ?? "\u2014"} | Maturity:{" "}
                              {loan.maturity_date ?? "\u2014"}
                            </div>
                            {loan.latest_snapshot && (
                              <div>
                                DSCR:{" "}
                                {fmtDscr(
                                  loan.latest_snapshot.dscr_noi ??
                                    loan.latest_snapshot
                                      .dscr_noi_at_securitization
                                )}{" "}
                                | Rate:{" "}
                                {loan.latest_snapshot.current_interest_rate != null
                                  ? `${(loan.latest_snapshot.current_interest_rate * 100).toFixed(2)}%`
                                  : "\u2014"}
                              </div>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Modified performing loans */}
      <div>
        <h3 className="text-sm font-semibold text-zinc-700 mb-1">
          Modified Loans (Performing)
        </h3>
        <p className="text-xs text-zinc-400 italic mb-2">
          Performing loans with restructured terms, currently with master
          servicer
        </p>
        {modifiedLoans.length === 0 ? (
          <div className="border border-zinc-200 rounded-md p-4 text-center text-sm text-zinc-400">
            No modified performing loans in current data
          </div>
        ) : null}
      </div>
    </div>
  );
}
