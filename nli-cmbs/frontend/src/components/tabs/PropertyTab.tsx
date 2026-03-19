import { useMemo, useState } from "react";
import { DonutChart } from "@/components/charts/DonutChart";
import { HBarChart } from "@/components/charts/HBarChart";
import { MetricCard } from "@/components/MetricCard";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PropertyTypeBadge } from "@/components/StatusBadge";
import type { Loan, LoanProperty } from "@/lib/types";
import {
  propertyTypeName,
  propertyTypeCategory,
  fmtBalance,
  fmtNoi,
  fmtOccupancy,
  fmtSqFt,
  loanBalance,
} from "@/lib/format";

interface PropertyTabProps {
  loans: Loan[];
}

interface FlatProperty extends LoanProperty {
  loanId: string;
  loanName: string | null;
  loanPropertyCount: number;
  loanBalance: number;
}

export function PropertyTab({ loans }: PropertyTabProps) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  // Flatten all properties from all loans
  const allProperties = useMemo<FlatProperty[]>(() => {
    const props: FlatProperty[] = [];
    for (const loan of loans) {
      if (loan.parent_loan_id) continue; // skip child notes
      const bal = loanBalance(loan);
      for (const p of loan.properties) {
        props.push({
          ...p,
          loanId: loan.id,
          loanName: loan.property_name,
          loanPropertyCount: loan.property_count,
          loanBalance: bal,
        });
      }
    }
    return props;
  }, [loans]);

  // Property type distribution by balance
  const typeData = useMemo(() => {
    const map = new Map<string, { balance: number; code: string }>();
    for (const loan of loans) {
      if (loan.parent_loan_id) continue;
      const cat = propertyTypeCategory(loan.property_type);
      const code = loan.property_type ?? "OT";
      const bal = loanBalance(loan);
      const existing = map.get(cat);
      if (existing) {
        existing.balance += bal;
      } else {
        map.set(cat, { balance: bal, code });
      }
    }
    return Array.from(map.entries())
      .map(([name, { balance, code }]) => ({ name, value: balance, code }))
      .sort((a, b) => b.value - a.value);
  }, [loans]);

  // State distribution by balance (top 7)
  const stateData = useMemo(() => {
    const map = new Map<string, number>();
    for (const loan of loans) {
      if (loan.parent_loan_id) continue;
      const state = loan.property_state ?? "N/A";
      const bal = loanBalance(loan);
      map.set(state, (map.get(state) ?? 0) + bal);
    }
    return Array.from(map.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 7);
  }, [loans]);

  const selectedProp = selectedIdx != null ? allProperties[selectedIdx] : null;

  // Find the loan for the selected property to check if it's a portfolio loan
  const selectedLoan = selectedProp
    ? loans.find((l) => l.id === selectedProp.loanId)
    : null;

  return (
    <div className="space-y-4">
      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border border-zinc-200 rounded-md p-4">
          <DonutChart data={typeData} title="By Property Type" />
        </div>
        <div className="border border-zinc-200 rounded-md p-4">
          <HBarChart data={stateData} title="By State (Top 7)" />
        </div>
      </div>

      {/* Property selector */}
      <div>
        <label className="text-xs font-medium text-zinc-500 uppercase tracking-wide block mb-1">
          Select Property
        </label>
        <select
          className="h-8 w-full max-w-md rounded-md border border-zinc-200 bg-white px-2 text-sm"
          value={selectedIdx ?? ""}
          onChange={(e) => {
            const val = e.target.value;
            setSelectedIdx(val === "" ? null : Number(val));
          }}
        >
          <option value="">Choose a property...</option>
          {allProperties.map((p, i) => (
            <option key={i} value={i}>
              {p.property_name ?? "Unnamed"} — {p.property_city ?? ""},{" "}
              {p.property_state ?? ""} ({propertyTypeName(p.property_type)})
            </option>
          ))}
        </select>
      </div>

      {selectedProp && (
        <div className="space-y-4">
          {/* Loan context banner - only for portfolio loans */}
          {selectedLoan && selectedLoan.property_count > 1 && (
            <div
              className="rounded-md px-4 py-2.5 text-sm text-zinc-600"
              style={{ backgroundColor: "rgba(128,128,128,0.08)" }}
            >
              Part of{" "}
              <span className="font-medium text-zinc-800">
                {selectedLoan.property_name ?? "Portfolio"}
              </span>
              {" \u2014 "}
              {selectedLoan.property_count} properties{" \u2014 "}
              {fmtBalance(selectedProp.loanBalance)} total
            </div>
          )}

          {/* Property header */}
          <div className="border border-zinc-200 rounded-md p-4">
            <div className="flex items-baseline gap-3">
              <h3 className="text-base font-semibold text-zinc-900">
                {selectedProp.property_name ?? "Unnamed Property"}
              </h3>
              <PropertyTypeBadge code={selectedProp.property_type} />
            </div>
            <div className="flex gap-4 mt-1 text-sm text-zinc-500">
              <span>
                {[selectedProp.property_city, selectedProp.property_state]
                  .filter(Boolean)
                  .join(", ") || "\u2014"}
              </span>
              {selectedProp.net_rentable_sq_ft && (
                <span>{fmtSqFt(selectedProp.net_rentable_sq_ft)}</span>
              )}
              {selectedProp.year_built && (
                <span>Built {selectedProp.year_built}</span>
              )}
            </div>
          </div>

          {/* Property metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <MetricCard
              label="Appraised Value"
              value={fmtBalance(selectedProp.valuation_securitization)}
            />
            <MetricCard
              label="NOI"
              value={fmtNoi(selectedProp.noi_most_recent)}
            />
            <MetricCard
              label="Occupancy"
              value={fmtOccupancy(selectedProp.occupancy_most_recent)}
            />
            <MetricCard
              label="Year Built"
              value={selectedProp.year_built?.toString() ?? "\u2014"}
            />
          </div>

          {/* Tenants */}
          {selectedProp.largest_tenant && (
            <div>
              <h3 className="text-sm font-semibold text-zinc-700 mb-2">
                Top Tenants
              </h3>
              <div className="border border-zinc-200 rounded-md overflow-auto">
                <Table>
                  <TableHeader className="bg-zinc-50">
                    <TableRow className="hover:bg-zinc-50">
                      <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                        #
                      </TableHead>
                      <TableHead className="text-[11px] uppercase font-medium text-zinc-500">
                        Tenant
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow className="text-sm">
                      <TableCell className="py-1.5 font-mono text-zinc-400">
                        1
                      </TableCell>
                      <TableCell className="py-1.5 font-medium">
                        {selectedProp.largest_tenant}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </div>
          )}
        </div>
      )}

      {!selectedProp && (
        <div className="border border-zinc-200 rounded-md p-8 text-center text-sm text-zinc-400">
          Select a property above to view details
        </div>
      )}
    </div>
  );
}
