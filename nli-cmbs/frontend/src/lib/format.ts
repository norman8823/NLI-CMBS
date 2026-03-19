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

/** Status badge config */
export function statusConfig(status: string | null | undefined): {
  label: string;
  bg: string;
  text: string;
} {
  const s = (status ?? "").toLowerCase();
  if (s.includes("specially") || s === "ss")
    return { label: "SS", bg: "#FEE2E2", text: "#991B1B" };
  if (s.includes("90") || s.includes("foreclosure") || s.includes("reo"))
    return { label: "90+", bg: "#FEE2E2", text: "#991B1B" };
  if (s.includes("60"))
    return { label: "60-day", bg: "#FFEDD5", text: "#9A3412" };
  if (s.includes("30"))
    return { label: "30-day", bg: "#FEF3C7", text: "#92400E" };
  return { label: "Current", bg: "#DCFCE7", text: "#166534" };
}

/** Get the current balance for a loan */
export function loanBalance(loan: {
  latest_snapshot?: { ending_balance: number | null } | null;
  original_loan_amount: number;
}): number {
  return loan.latest_snapshot?.ending_balance ?? loan.original_loan_amount;
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
