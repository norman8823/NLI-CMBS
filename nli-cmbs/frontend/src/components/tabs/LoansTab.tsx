import { useState, useMemo, useRef, useEffect } from "react";
import { StatusBadge, PropertyTypeBadge } from "@/components/StatusBadge";
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
  fmtPct,
  fmtMonthYear,
  loanBalance,
  propertyTypeName,
  propertyTypeCategory,
  statusConfig,
} from "@/lib/format";

interface LoansTabProps {
  loans: Loan[];
}

type SortKey =
  | "property"
  | "type"
  | "location"
  | "balance"
  | "orig_bal"
  | "rate"
  | "io"
  | "dscr"
  | "ltv"
  | "status"
  | "orig_date"
  | "maturity";
type SortDir = "asc" | "desc";

const PROPERTY_TYPES = ["Office", "Retail", "Multifamily", "Industrial", "Hotel", "Other"];
const STATUSES = ["Current", "30-day", "60-day", "90+", "SS"];

function getSortVal(loan: Loan, key: SortKey): string | number | null {
  switch (key) {
    case "property":
      return loan.property_name;
    case "type":
      return propertyTypeName(loan.property_type);
    case "location":
      return loan.property_state;
    case "balance":
      return loanBalance(loan);
    case "orig_bal":
      return loan.original_loan_amount;
    case "rate":
      return (
        loan.latest_snapshot?.current_interest_rate ??
        loan.original_interest_rate
      );
    case "io":
      return loan.interest_only_indicator ? 1 : 0;
    case "dscr":
      return (
        loan.latest_snapshot?.dscr_noi ??
        loan.latest_snapshot?.dscr_noi_at_securitization ??
        null
      );
    case "ltv":
      return computeLtv(loan);
    case "status":
      return statusConfig(loan.latest_snapshot?.delinquency_status).label;
    case "orig_date":
      return loan.origination_date;
    case "maturity":
      return loan.maturity_date;
    default:
      return null;
  }
}

function computeLtv(loan: Loan): number | null {
  const bal = loanBalance(loan);
  const val = loan.latest_snapshot?.appraised_value;
  if (val == null || val === 0) return null;
  return (bal / val) * 100;
}

function matchesTypeFilter(loan: Loan, filters: Set<string>): boolean {
  if (filters.size === 0) return true;
  const cat = propertyTypeCategory(loan.property_type);
  return filters.has(cat);
}

function matchesStatusFilter(loan: Loan, filters: Set<string>): boolean {
  if (filters.size === 0) return true;
  const cfg = statusConfig(loan.latest_snapshot?.delinquency_status);
  return filters.has(cfg.label);
}

function FilterDropdown({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: string[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const toggle = (opt: string) => {
    const next = new Set(selected);
    if (next.has(opt)) next.delete(opt);
    else next.add(opt);
    onChange(next);
  };

  return (
    <div ref={ref} className="relative inline-block">
      <button
        className={`text-[11px] uppercase font-medium tracking-wide ${
          selected.size > 0 ? "text-blue-600" : "text-zinc-500"
        }`}
        onClick={() => setOpen(!open)}
      >
        {label} {selected.size > 0 ? `(${selected.size})` : ""} ▾
      </button>
      {open && (
        <div className="absolute z-50 top-6 left-0 bg-white border border-zinc-200 rounded-md shadow-md p-2 min-w-[140px]">
          {options.map((opt) => (
            <label
              key={opt}
              className="flex items-center gap-2 text-xs py-0.5 cursor-pointer hover:bg-zinc-50 px-1 rounded"
            >
              <input
                type="checkbox"
                checked={selected.has(opt)}
                onChange={() => toggle(opt)}
                className="rounded border-zinc-300"
              />
              {opt}
            </label>
          ))}
          {selected.size > 0 && (
            <button
              className="text-[10px] text-blue-600 mt-1 px-1"
              onClick={() => onChange(new Set())}
            >
              Clear
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function LoansTab({ loans }: LoansTabProps) {
  const [sortKey, setSortKey] = useState<SortKey>("balance");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());
  const [statusFilter, setStatusFilter] = useState<Set<string>>(new Set());

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const activeLoans = useMemo(
    () => loans.filter((l) => !l.parent_loan_id),
    [loans]
  );

  const filtered = useMemo(() => {
    return activeLoans.filter(
      (l) => matchesTypeFilter(l, typeFilter) && matchesStatusFilter(l, statusFilter)
    );
  }, [activeLoans, typeFilter, statusFilter]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = getSortVal(a, sortKey);
      const bv = getSortVal(b, sortKey);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  const indicator = (key: SortKey) =>
    sortKey === key ? (sortDir === "asc" ? " \u2191" : " \u2193") : "";

  const columns: {
    key: SortKey;
    label: string;
    align?: "right";
    filter?: React.ReactNode;
  }[] = [
    { key: "property", label: "Properties" },
    {
      key: "type",
      label: "Type",
      filter: (
        <FilterDropdown
          label="Type"
          options={PROPERTY_TYPES}
          selected={typeFilter}
          onChange={setTypeFilter}
        />
      ),
    },
    { key: "location", label: "Location" },
    { key: "balance", label: "Balance", align: "right" },
    { key: "orig_bal", label: "Orig Bal", align: "right" },
    { key: "rate", label: "Rate", align: "right" },
    { key: "io", label: "IO" },
    { key: "dscr", label: "DSCR", align: "right" },
    { key: "ltv", label: "LTV", align: "right" },
    {
      key: "status",
      label: "Status",
      filter: (
        <FilterDropdown
          label="Status"
          options={STATUSES}
          selected={statusFilter}
          onChange={setStatusFilter}
        />
      ),
    },
    { key: "orig_date", label: "Orig" },
    { key: "maturity", label: "Maturity" },
  ];

  return (
    <div className="space-y-2">
      <div className="text-sm text-zinc-600">
        {sorted.length} loan{sorted.length !== 1 ? "s" : ""}
        {(typeFilter.size > 0 || statusFilter.size > 0) && (
          <span className="text-zinc-400 ml-1">(filtered)</span>
        )}
      </div>

      <div className="border border-zinc-200 rounded-md overflow-auto max-h-[calc(100vh-220px)]">
        <Table>
          <TableHeader className="bg-zinc-50 sticky top-0 z-10">
            <TableRow className="hover:bg-zinc-50">
              {columns.map((col) => (
                <TableHead
                  key={col.key}
                  className={`text-[11px] uppercase font-medium text-zinc-500 ${
                    col.align === "right" ? "text-right" : ""
                  }`}
                >
                  {col.filter ? (
                    col.filter
                  ) : (
                    <button
                      className="cursor-pointer select-none"
                      onClick={() => toggleSort(col.key)}
                    >
                      {col.label}
                      {indicator(col.key)}
                    </button>
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((loan, i) => {
              const bal = loanBalance(loan);
              const rate =
                loan.latest_snapshot?.current_interest_rate ??
                loan.original_interest_rate;
              const currentDscr = loan.latest_snapshot?.dscr_noi ?? null;
              const dscr = currentDscr ?? loan.latest_snapshot?.dscr_noi_at_securitization ?? null;
              const dscrIsSecuritization = currentDscr == null && dscr != null;
              const ltv = computeLtv(loan);
              const location = [loan.property_city, loan.property_state]
                .filter(Boolean)
                .join(", ");
              const propName =
                loan.property_count > 1
                  ? `${loan.property_name ?? "Portfolio"} (${loan.property_count})`
                  : loan.property_name ?? "\u2014";

              return (
                <TableRow
                  key={loan.id ?? i}
                  className={`text-sm ${i % 2 === 0 ? "bg-white" : "bg-zinc-50/50"}`}
                >
                  <TableCell className="py-1.5 font-medium text-sm max-w-[180px] truncate">
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
                  <TableCell className="py-1.5 text-right font-mono text-sm text-zinc-500">
                    {fmtBalance(loan.original_loan_amount)}
                  </TableCell>
                  <TableCell className="py-1.5 text-right font-mono text-sm">
                    {fmtRate(rate)}
                  </TableCell>
                  <TableCell className="py-1.5 text-sm">
                    {loan.interest_only_indicator ? (
                      <span className="text-[11px] px-1 py-0.5 rounded bg-blue-50 text-blue-700">
                        IO
                      </span>
                    ) : (
                      <span className="text-zinc-400">\u2014</span>
                    )}
                  </TableCell>
                  <TableCell className="py-1.5 text-right font-mono text-sm">
                    <span
                      className={
                        dscr != null && dscr < 1.25 ? "text-rose-600" : dscrIsSecuritization ? "text-zinc-400" : ""
                      }
                      title={dscrIsSecuritization ? "At securitization" : undefined}
                    >
                      {fmtDscr(dscr)}
                      {dscrIsSecuritization && <sup className="text-[9px] ml-0.5">s</sup>}
                    </span>
                  </TableCell>
                  <TableCell className="py-1.5 text-right font-mono text-sm">
                    <span
                      className={
                        ltv != null && ltv > 75 ? "text-amber-600" : ""
                      }
                    >
                      {ltv != null ? fmtPct(ltv) : "\u2014"}
                    </span>
                  </TableCell>
                  <TableCell className="py-1.5">
                    <StatusBadge
                      status={loan.latest_snapshot?.delinquency_status}
                    />
                  </TableCell>
                  <TableCell className="py-1.5 text-sm font-mono text-zinc-500">
                    {fmtMonthYear(loan.origination_date)}
                  </TableCell>
                  <TableCell className="py-1.5 text-sm font-mono">
                    {fmtMonthYear(loan.maturity_date)}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
