import type { DealDetail } from "@/lib/types";
import { fmtDate } from "@/lib/format";

interface DealHeaderProps {
  deal: DealDetail;
}

export function DealHeader({ deal }: DealHeaderProps) {
  const edgarUrl = `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${deal.depositor_cik}&type=ABS-EE`;

  return (
    <div className="flex items-baseline gap-4">
      <h1 className="text-2xl font-bold tracking-tight text-foreground">
        {deal.ticker}
      </h1>
      <span className="text-sm text-zinc-500">{deal.trust_name}</span>
      {deal.last_filing_date && (
        <span className="text-xs text-zinc-400">
          Filed {fmtDate(deal.last_filing_date)}
        </span>
      )}
      <a
        href={edgarUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-blue-600 hover:text-blue-800 underline ml-auto"
      >
        EDGAR
      </a>
    </div>
  );
}
