/** Shared formatting utilities */

export function fmtBalance(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

export function fmtPct(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return `${value.toFixed(2)}%`;
}

export function fmtRate(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  // Handle rates stored as decimals (0.045 = 4.5%) vs already as percentages (4.5)
  const pct = value < 1 ? value * 100 : value;
  return `${pct.toFixed(2)}%`;
}

export function fmtDscr(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return `${value.toFixed(2)}x`;
}

export function fmtDate(d: string | null | undefined): string {
  if (!d) return "\u2014";
  return new Date(d + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function fmtMonthYear(d: string | null | undefined): string {
  if (!d) return "\u2014";
  return new Date(d + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    year: "numeric",
  });
}

export function fmtSqFt(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return value.toLocaleString("en-US", { maximumFractionDigits: 0 }) + " SF";
}

export function fmtOccupancy(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  const pct = value <= 1 ? value * 100 : value;
  return `${pct.toFixed(1)}%`;
}

export function fmtNoi(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
  if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

/** Property type code to display name */
const PROPERTY_TYPE_MAP: Record<string, string> = {
  CH: "Cooperative Housing",
  HC: "Healthcare",
  HT: "Hotel",
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

export function propertyTypeName(code: string | null | undefined): string {
  if (!code) return "Other";
  return PROPERTY_TYPE_MAP[code] ?? code;
}

/** Map property type to canonical category for badge coloring */
export function propertyTypeCategory(
  code: string | null | undefined
): "Office" | "Retail" | "Multifamily" | "Industrial" | "Hotel" | "Other" {
  if (!code) return "Other";
  switch (code) {
    case "OF":
      return "Office";
    case "RT":
      return "Retail";
    case "MF":
      return "Multifamily";
    case "IN":
    case "WH":
      return "Industrial";
    case "HT":
    case "LO":
      return "Hotel";
    default:
      return "Other";
  }
}

/** Badge colors by property type category */
export const PROPERTY_TYPE_COLORS: Record<
  string,
  { bg: string; text: string }
> = {
  Office: { bg: "#E6F1FB", text: "#0C447C" },
  Retail: { bg: "#E1F5EE", text: "#085041" },
  Multifamily: { bg: "#FAECE7", text: "#712B13" },
  Industrial: { bg: "#EEEDFE", text: "#3C3489" },
  Hotel: { bg: "#FBEAF0", text: "#72243E" },
  Other: { bg: "#F4F4F5", text: "#52525B" },
};

/**
 * Canonical delinquency status mapping.
 * ABS-EE XML stores codes: "0","1","2","3","4","5","A","B", not human-readable strings.
 */
export interface DelinquencyInfo {
  label: string;
  severity: number;  // 0=current, 1=30, 2=60, 3=90+, 4=foreclosure/bankruptcy, 5=matured
  color: string;     // tailwind text color class
  bgColor: string;   // tailwind badge background class
  isDelinquent: boolean;
  isSpeciallyServiced: boolean;
}

export function getDelinquencyInfo(status: string | null | undefined): DelinquencyInfo {
  const code = (status ?? "0").trim();
  switch (code) {
    case "1":
      return { label: "30-Day", severity: 1, color: "text-amber-700", bgColor: "bg-amber-100 text-amber-800", isDelinquent: true, isSpeciallyServiced: false };
    case "2":
      return { label: "60-Day", severity: 2, color: "text-orange-700", bgColor: "bg-orange-100 text-orange-800", isDelinquent: true, isSpeciallyServiced: false };
    case "3":
      return { label: "90+", severity: 3, color: "text-rose-700", bgColor: "bg-rose-100 text-rose-800", isDelinquent: true, isSpeciallyServiced: true };
    case "4":
      return { label: "Bankruptcy", severity: 4, color: "text-rose-700", bgColor: "bg-rose-100 text-rose-800", isDelinquent: true, isSpeciallyServiced: true };
    case "5":
      return { label: "FC/REO", severity: 5, color: "text-rose-700", bgColor: "bg-rose-100 text-rose-800", isDelinquent: true, isSpeciallyServiced: true };
    case "A":
      return { label: "Non-Performing", severity: 4, color: "text-rose-700", bgColor: "bg-rose-100 text-rose-800", isDelinquent: true, isSpeciallyServiced: true };
    case "B":
      return { label: "Balloon", severity: 0, color: "text-blue-600", bgColor: "bg-blue-50 text-blue-700", isDelinquent: false, isSpeciallyServiced: false };
    case "0":
    default:
      return { label: "Current", severity: 0, color: "text-emerald-700", bgColor: "bg-zinc-100 text-zinc-700", isDelinquent: false, isSpeciallyServiced: false };
  }
}

/** Returns true for balloon loan codes: "A" (non-performing) and "B" (performing) */
export function isBalloonLoan(status: string | null | undefined): boolean {
  const code = (status ?? "0").trim();
  return code === "B" || code === "A";
}

/** Returns true if a loan is past its maturity date and still has a balance */
export function isMaturityDefault(loan: { maturity_date?: string | null; latest_snapshot?: { ending_balance?: number | null } | null }): boolean {
  if (!loan.maturity_date) return false;
  const maturity = new Date(loan.maturity_date);
  const today = new Date();
  const balance = loan.latest_snapshot?.ending_balance ?? 0;
  return maturity < today && balance > 0;
}

/** Status badge config — uses canonical delinquency mapping */
export function statusConfig(status: string | null | undefined): {
  label: string;
  bg: string;
  text: string;
} {
  const info = getDelinquencyInfo(status);
  const code = (status ?? "0").trim();
  // Map severity to hex badge colors for StatusBadge component
  if (code === "B") return { label: info.label, bg: "#DBEAFE", text: "#1D4ED8" }; // blue for Balloon
  if (info.severity >= 3) return { label: info.label, bg: "#FEE2E2", text: "#991B1B" };
  if (info.severity === 2) return { label: info.label, bg: "#FFEDD5", text: "#9A3412" };
  if (info.severity === 1) return { label: info.label, bg: "#FEF3C7", text: "#92400E" };
  return { label: info.label, bg: "#DCFCE7", text: "#166534" };
}

/** Get the current balance for a loan */
export function loanBalance(loan: {
  latest_snapshot?: { ending_balance: number | null } | null;
  original_loan_amount: number;
}): number {
  return loan.latest_snapshot?.ending_balance ?? loan.original_loan_amount;
}

/** Fallback chain for displaying a loan's name */
export function loanDisplayName(loan: {
  property_name?: string | null;
  parent_loan_id?: string | null;
  parent_prospectus_loan_id?: string | null;
  property_city?: string | null;
  property_state?: string | null;
  prospectus_loan_id: string;
}): string {
  if (loan.property_name) return loan.property_name;
  if (loan.parent_loan_id) return "See Loan " + (loan.parent_prospectus_loan_id ?? "parent");
  const loc = [loan.property_city, loan.property_state].filter(Boolean).join(", ");
  if (loc) return loc;
  return "Loan " + loan.prospectus_loan_id;
}

/** Months between now and a date string */
export function monthsUntil(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null;
  const target = new Date(dateStr + "T00:00:00");
  const now = new Date();
  return (
    (target.getFullYear() - now.getFullYear()) * 12 +
    (target.getMonth() - now.getMonth())
  );
}
