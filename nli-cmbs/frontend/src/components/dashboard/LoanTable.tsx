import { useState, useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PropertyModal } from "./PropertyModal";
import type { Loan } from "@/lib/types";
import { getDelinquencyInfo } from "@/lib/format";

function formatBalance(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

type SortKey =
  | "loan_id"
  | "property"
  | "current_balance"
  | "interest_rate"
  | "maturity_date"
  | "dscr"
  | "delinquency";
type SortDir = "asc" | "desc";

function getSortValue(loan: Loan, key: SortKey): string | number | null {
  switch (key) {
    case "loan_id":
      return loan.asset_number;
    case "property":
      return loan.property_name;
    case "current_balance":
      return loan.latest_snapshot?.ending_balance ?? loan.original_loan_amount;
    case "interest_rate":
      return (
        loan.latest_snapshot?.current_interest_rate ??
        loan.original_interest_rate
      );
    case "maturity_date":
      return loan.maturity_date;
    case "dscr":
      return loan.latest_snapshot?.dscr_noi ?? loan.latest_snapshot?.dscr_noi_at_securitization ?? null;
    case "delinquency":
      return loan.latest_snapshot?.delinquency_status ?? "0";
    default:
      return null;
  }
}

interface LoanTableProps {
  loans: Loan[];
}

export function LoanTable({ loans }: LoanTableProps) {
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("current_balance");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [selectedLoan, setSelectedLoan] = useState<Loan | null>(null);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sorted = useMemo(() => {
    const filtered = filter
      ? loans.filter(
          (l) =>
            l.property_name?.toLowerCase().includes(filter.toLowerCase()) ||
            l.prospectus_loan_id.toLowerCase().includes(filter.toLowerCase())
        )
      : loans;
    return [...filtered].sort((a, b) => {
      const av = getSortValue(a, sortKey);
      const bv = getSortValue(b, sortKey);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [loans, filter, sortKey, sortDir]);

  const sortIndicator = (key: SortKey) =>
    sortKey === key ? (sortDir === "asc" ? " \u2191" : " \u2193") : "";

  const maturityFmt = (d: string | null | undefined) => {
    if (!d) return "\u2014";
    const date = new Date(d);
    return date.toLocaleDateString("en-US", {
      month: "short",
      year: "numeric",
    });
  };

  const columns: { key: SortKey; label: string; align?: "right" }[] = [
    { key: "loan_id", label: "Loan ID" },
    { key: "property", label: "Property" },
    { key: "current_balance", label: "Balance", align: "right" },
    { key: "interest_rate", label: "Rate", align: "right" },
    { key: "maturity_date", label: "Maturity", align: "right" },
    { key: "dscr", label: "DSCR", align: "right" },
  ];

  const getBalance = (loan: Loan) =>
    loan.latest_snapshot?.ending_balance ?? loan.original_loan_amount;

  const getInterestRate = (loan: Loan) =>
    loan.latest_snapshot?.current_interest_rate ?? loan.original_interest_rate;

  const getDscr = (loan: Loan) =>
    loan.latest_snapshot?.dscr_noi ?? loan.latest_snapshot?.dscr_noi_at_securitization ?? null;

  const getDelinquencyStatus = (loan: Loan) =>
    loan.latest_snapshot?.delinquency_status;

  /** Render the clickable Property cell content */
  const renderPropertyCell = (loan: Loan) => {
    if (loan.parent_loan_id) {
      return (
        <span className="text-zinc-400 italic text-xs">
          See Loan {loan.parent_prospectus_loan_id ?? "parent"}
        </span>
      );
    }
    if (loan.property_count > 1) {
      return (
        <span className="text-blue-600 hover:text-blue-800 underline-offset-2 hover:underline">
          {loan.property_count} properties
        </span>
      );
    }
    return (
      <span className="hover:text-blue-700 hover:underline underline-offset-2 max-w-[200px] truncate block">
        {loan.property_name ?? "\u2014"}
      </span>
    );
  };

  const handlePropertyClick = (loan: Loan) => {
    // For child notes, try to open the parent loan's modal
    if (loan.parent_loan_id) {
      const parent = loans.find((l) => l.id === loan.parent_loan_id);
      if (parent) {
        setSelectedLoan(parent);
        return;
      }
    }
    setSelectedLoan(loan);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-zinc-600">
          {sorted.length} loan{sorted.length !== 1 ? "s" : ""}
        </span>
        <Input
          placeholder="Filter by loan ID or property\u2026"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="h-8 w-56 text-sm"
        />
      </div>
      <div className="border border-border rounded-md overflow-auto max-h-[600px]">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-zinc-100">
            <TableRow className="hover:bg-zinc-100">
              {columns.map((col) => (
                <TableHead
                  key={col.key}
                  className={`cursor-pointer select-none uppercase text-xs font-medium text-zinc-600 ${
                    col.align === "right" ? "text-right" : ""
                  }`}
                  onClick={() => toggleSort(col.key)}
                >
                  {col.label}
                  {sortIndicator(col.key)}
                </TableHead>
              ))}
              <TableHead className="uppercase text-xs font-medium text-zinc-600">
                Status
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((loan, i) => {
              const badge = getDelinquencyInfo(getDelinquencyStatus(loan));
              const rate = getInterestRate(loan);
              const dscr = getDscr(loan);
              return (
                <TableRow
                  key={loan.id ?? loan.prospectus_loan_id ?? i}
                  className={`text-sm ${i % 2 === 0 ? "bg-white" : "bg-zinc-50"}`}
                >
                  <TableCell className="py-2 font-mono text-xs text-zinc-500">
                    {loan.prospectus_loan_id}
                  </TableCell>
                  <TableCell
                    className="py-2 font-medium cursor-pointer"
                    onClick={() => handlePropertyClick(loan)}
                  >
                    {renderPropertyCell(loan)}
                  </TableCell>
                  <TableCell className="py-2 text-right font-mono">
                    {formatBalance(getBalance(loan))}
                  </TableCell>
                  <TableCell className="py-2 text-right font-mono">
                    {rate != null ? `${(rate * 100).toFixed(2)}%` : "\u2014"}
                  </TableCell>
                  <TableCell className="py-2 text-right font-mono">
                    {maturityFmt(loan.maturity_date)}
                  </TableCell>
                  <TableCell className="py-2 text-right font-mono">
                    {dscr != null ? `${dscr.toFixed(2)}x` : "\u2014"}
                  </TableCell>
                  <TableCell className="py-2">
                    <Badge
                      variant="outline"
                      className={`text-[11px] px-1.5 py-0 border-0 ${badge.bgColor}`}
                    >
                      {badge.label}
                    </Badge>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <PropertyModal
        loan={selectedLoan}
        onClose={() => setSelectedLoan(null)}
        allLoans={loans}
        onSelectLoan={setSelectedLoan}
      />
    </div>
  );
}
