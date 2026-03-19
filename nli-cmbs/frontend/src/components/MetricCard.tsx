import { Card, CardContent } from "@/components/ui/card";

interface MetricCardProps {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}

export function MetricCard({ label, value, sub, color }: MetricCardProps) {
  return (
    <Card className="shadow-none border-zinc-200 rounded-md py-0 gap-0">
      <CardContent className="p-3">
        <p className="text-[11px] uppercase tracking-wide text-zinc-500 leading-none mb-1">
          {label}
        </p>
        <p
          className={`text-xl font-semibold tabular-nums leading-tight ${color ?? "text-foreground"}`}
        >
          {value}
        </p>
        {sub && (
          <p className="text-[11px] text-zinc-400 mt-0.5 tabular-nums">
            {sub}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
