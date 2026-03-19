// NOTE: This component is not currently used — OverviewTab replaced it.
// Kept for potential reuse.
import { Card, CardContent } from "@/components/ui/card";
import type { DealDetail } from "@/lib/types";
import { getDelinquencyInfo } from "@/lib/format";

function formatBalance(value: number): string {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
}

function delinquencyColor(rate: number): string {
  if (rate > 5) return "text-rose-600";
  if (rate >= 2) return "text-amber-600";
  return "text-emerald-600";
}

function computeSpeciallyServiced(
  delinquencyByStatus: Record<string, number> | null,
  loanCount: number
): number {
  if (!delinquencyByStatus || !loanCount) return 0;
  // ABS-EE codes: "3"=90+, "4"=bankruptcy, "5"=FC/REO, "A"=NP matured are SS
  const ssCount = Object.entries(delinquencyByStatus)
    .filter(([status]) => getDelinquencyInfo(status).isSpeciallyServiced)
    .reduce((sum, [, count]) => sum + count, 0);
  return (ssCount / loanCount) * 100;
}

interface MetricsCardsProps {
  deal: DealDetail;
}

export function MetricsCards({ deal }: MetricsCardsProps) {
  const ssRate = computeSpeciallyServiced(
    deal.delinquency_by_status,
    deal.loan_count ?? 0
  );

  const metrics = [
    {
      label: "CURRENT UPB",
      value: deal.total_upb ? formatBalance(deal.total_upb) : "—",
    },
    {
      label: "LOAN COUNT",
      value: deal.loan_count?.toLocaleString() ?? "—",
    },
    {
      label: "WA COUPON",
      value: deal.wa_coupon != null ? `${deal.wa_coupon.toFixed(2)}%` : "—",
    },
    {
      label: "WA DSCR",
      value: deal.wa_dscr != null ? `${deal.wa_dscr.toFixed(2)}x` : "—",
    },
    {
      label: "DELINQUENCY RATE",
      value:
        deal.delinquency_rate != null
          ? `${deal.delinquency_rate.toFixed(2)}%`
          : "—",
      color:
        deal.delinquency_rate != null
          ? delinquencyColor(deal.delinquency_rate)
          : undefined,
    },
    {
      label: "SPECIALLY SERVICED",
      value: `${ssRate.toFixed(2)}%`,
      color: delinquencyColor(ssRate),
    },
  ];

  const filingDate = deal.last_filing_date
    ? new Date(deal.last_filing_date + "T00:00:00").toLocaleDateString(
        "en-US",
        { month: "short", day: "numeric", year: "numeric" }
      )
    : null;

  const edgarUrl = `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${deal.depositor_cik}&type=ABS-EE`;

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
        {metrics.map((m) => (
          <Card
            key={m.label}
            className="shadow-none border-zinc-200 rounded-md py-0 gap-0"
          >
            <CardContent className="p-3">
              <p className="text-xs uppercase tracking-wide text-zinc-500 leading-none mb-1">
                {m.label}
              </p>
              <p
                className={`text-2xl font-semibold tabular-nums ${m.color ?? "text-foreground"}`}
              >
                {m.value}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
      {filingDate && (
        <p className="text-xs text-zinc-400">
          Source: ABS-EE filing dated {filingDate}
          {deal.last_filing_accession && (
            <>
              {" "}
              | Accession No. {deal.last_filing_accession}
            </>
          )}
          {" | "}
          <a
            href={edgarUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-zinc-600"
          >
            View on EDGAR
          </a>
        </p>
      )}
    </div>
  );
}
