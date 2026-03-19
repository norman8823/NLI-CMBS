import {
  statusConfig,
  propertyTypeName,
  propertyTypeCategory,
  PROPERTY_TYPE_COLORS,
} from "@/lib/format";

interface StatusBadgeProps {
  status: string | null | undefined;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const cfg = statusConfig(status);
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium"
      style={{ backgroundColor: cfg.bg, color: cfg.text }}
    >
      {cfg.label}
    </span>
  );
}

interface PropertyTypeBadgeProps {
  code: string | null | undefined;
}

export function PropertyTypeBadge({ code }: PropertyTypeBadgeProps) {
  const category = propertyTypeCategory(code);
  const colors = PROPERTY_TYPE_COLORS[category];
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium"
      style={{ backgroundColor: colors.bg, color: colors.text }}
    >
      {propertyTypeName(code)}
    </span>
  );
}

interface MonthsBadgeProps {
  months: number | null;
}

export function MonthsBadge({ months }: MonthsBadgeProps) {
  if (months == null) return <span className="text-zinc-400">{"\u2014"}</span>;
  if (months < 0) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-red-100 text-red-800">
        Matured
      </span>
    );
  }
  let bg: string, text: string;
  if (months <= 3) {
    bg = "#FEE2E2";
    text = "#991B1B";
  } else if (months <= 6) {
    bg = "#FEF3C7";
    text = "#92400E";
  } else {
    bg = "#F4F4F5";
    text = "#52525B";
  }
  return (
    <span
      className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium"
      style={{ backgroundColor: bg, color: text }}
    >
      {months}mo
    </span>
  );
}
