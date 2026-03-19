import {
  Dialog,
  DialogHeader,
  DialogBody,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Loan, LoanProperty } from "@/lib/types";

function fmt(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  if (Math.abs(value) >= 1_000_000)
    return `$${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

function fmtSqFt(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function fmtPct(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  // Values stored as decimals (0.73 = 73%) — display as percentage
  const pct = value <= 1 ? value * 100 : value;
  return `${pct.toFixed(1)}%`;
}

function fmtBalance(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

function fmtRate(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return `${(value * 100).toFixed(2)}%`;
}

function fmtMaturity(d: string | null | undefined): string {
  if (!d) return "\u2014";
  const date = new Date(d);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function fmtDscr(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return `${value.toFixed(2)}x`;
}

const PROPERTY_TYPES: Record<string, string> = {
  CH: "Cooperative Housing",
  HC: "Healthcare",
  HT: "Hospitality",
  IN: "Industrial",
  LO: "Lodging",
  MF: "Multifamily",
  MH: "Mobile Home",
  MU: "Mixed Use",
  OF: "Office",
  OT: "Other",
  RT: "Retail",
  SE: "Securities",
  SS: "Self Storage",
  WH: "Warehouse",
  ZZ: "Other",
  "98": "Other",
};

function propertyType(code: string | null | undefined): string {
  if (!code) return "\u2014";
  return PROPERTY_TYPES[code] ?? code;
}

function isNonReported(source: string | null | undefined): boolean {
  return source === "inferred" || source === "researched";
}

function sourceLabel(source: string | null | undefined): string {
  if (source === "inferred") return "Inferred from property name";
  if (source === "researched") return "Researched — not from SEC filing";
  return "";
}

interface PropertyModalProps {
  loan: Loan | null;
  onClose: () => void;
  /** All loans in the deal, for navigating to parent */
  allLoans: Loan[];
  onSelectLoan: (loan: Loan) => void;
}

export function PropertyModal({
  loan,
  onClose,
  allLoans,
  onSelectLoan,
}: PropertyModalProps) {
  if (!loan) return null;

  const isChildNote = !!loan.parent_loan_id;
  const properties: LoanProperty[] = isChildNote
    ? (loan.parent_properties ?? [])
    : (loan.properties ?? []);
  const parentLoan = isChildNote
    ? allLoans.find((l) => l.id === loan.parent_loan_id)
    : null;

  const snapshot = loan.latest_snapshot;
  const balance = snapshot?.ending_balance ?? loan.original_loan_amount;
  const rate = snapshot?.current_interest_rate ?? loan.original_interest_rate;
  const dscr = snapshot?.dscr_noi ?? snapshot?.dscr_noi_at_securitization ?? null;

  const title =
    loan.property_count > 1
      ? `Loan ${loan.prospectus_loan_id} \u2014 Portfolio`
      : `Loan ${loan.prospectus_loan_id} \u2014 ${loan.property_name ?? "Property Details"}`;

  return (
    <Dialog open={!!loan} onClose={onClose}>
      <DialogHeader>
        <h2 className="text-base font-semibold text-zinc-900">{title}</h2>
        <div className="flex gap-6 mt-2 text-sm text-zinc-600">
          <span>
            Balance: <span className="font-mono font-medium text-zinc-900">{fmtBalance(balance)}</span>
          </span>
          <span>
            Rate: <span className="font-mono font-medium text-zinc-900">{fmtRate(rate)}</span>
          </span>
          <span>
            Maturity: <span className="font-mono font-medium text-zinc-900">{fmtMaturity(loan.maturity_date)}</span>
          </span>
          <span>
            DSCR: <span className="font-mono font-medium text-zinc-900">{fmtDscr(dscr)}</span>
          </span>
        </div>
      </DialogHeader>

      <DialogBody>
        {isChildNote && parentLoan && (
          <p className="text-sm text-zinc-500 mb-3 italic">
            Properties from parent{" "}
            <button
              className="underline text-blue-600 hover:text-blue-800"
              onClick={() => onSelectLoan(parentLoan)}
            >
              Loan {loan.parent_prospectus_loan_id}
            </button>
          </p>
        )}

        {isChildNote && !parentLoan && loan.parent_prospectus_loan_id && (
          <p className="text-sm text-zinc-500 mb-3 italic">
            Properties from parent Loan {loan.parent_prospectus_loan_id}
          </p>
        )}

        {properties.length === 0 ? (
          <p className="text-sm text-zinc-400 py-8 text-center">
            No property details available for this loan.
          </p>
        ) : (
          <>
            <div className="border border-zinc-200 rounded-md overflow-auto">
              <Table>
                <TableHeader className="bg-zinc-50">
                  <TableRow className="hover:bg-zinc-50">
                    <TableHead className="text-xs uppercase font-medium text-zinc-600">Property Name</TableHead>
                    <TableHead className="text-xs uppercase font-medium text-zinc-600">City</TableHead>
                    <TableHead className="text-xs uppercase font-medium text-zinc-600">State</TableHead>
                    <TableHead className="text-xs uppercase font-medium text-zinc-600">Type</TableHead>
                    <TableHead className="text-xs uppercase font-medium text-zinc-600 text-right">Sq Ft</TableHead>
                    <TableHead className="text-xs uppercase font-medium text-zinc-600 text-right">Year Built</TableHead>
                    <TableHead className="text-xs uppercase font-medium text-zinc-600 text-right">Valuation</TableHead>
                    <TableHead className="text-xs uppercase font-medium text-zinc-600 text-right">Occupancy</TableHead>
                    <TableHead className="text-xs uppercase font-medium text-zinc-600 text-right">NOI</TableHead>
                    <TableHead className="text-xs uppercase font-medium text-zinc-600">Largest Tenant</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {properties.map((prop, i) => (
                    <TableRow
                      key={i}
                      className={`text-sm ${i % 2 === 0 ? "bg-white" : "bg-zinc-50"}`}
                    >
                      <TableCell className="py-2 font-medium max-w-[200px] truncate">
                        {prop.property_name ?? "\u2014"}
                      </TableCell>
                      <TableCell className="py-2">
                        {prop.property_city ?? "\u2014"}
                      </TableCell>
                      <TableCell className="py-2">
                        {prop.property_state ?? "\u2014"}
                      </TableCell>
                      <TableCell className="py-2">
                        {propertyType(prop.property_type)}
                        {isNonReported(prop.property_type_source) && (
                          <span className="text-amber-500 ml-0.5" title={sourceLabel(prop.property_type_source)}>*</span>
                        )}
                      </TableCell>
                      <TableCell className="py-2 text-right font-mono">
                        {fmtSqFt(prop.net_rentable_sq_ft)}
                      </TableCell>
                      <TableCell className="py-2 text-right font-mono">
                        {prop.year_built ?? "\u2014"}
                      </TableCell>
                      <TableCell className="py-2 text-right font-mono">
                        {fmt(prop.valuation_securitization)}
                      </TableCell>
                      <TableCell className="py-2 text-right font-mono">
                        {fmtPct(prop.occupancy_most_recent)}
                      </TableCell>
                      <TableCell className="py-2 text-right font-mono">
                        {fmt(prop.noi_most_recent)}
                      </TableCell>
                      <TableCell className="py-2 max-w-[180px] truncate">
                        {prop.largest_tenant ?? "\u2014"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {properties.some((p) => isNonReported(p.property_type_source)) && (
              <p className="text-xs text-amber-600 mt-2">
                <span className="font-medium">*</span> Property type not from SEC filing — inferred from name or independently researched.
              </p>
            )}
          </>
        )}
      </DialogBody>

      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          Close
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
