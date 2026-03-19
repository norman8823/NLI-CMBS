import { useState, useRef, useEffect } from "react";
import { Input } from "@/components/ui/input";
import type { DealListItem } from "@/lib/types";

interface DealSearchProps {
  deals: DealListItem[] | undefined;
  isLoading: boolean;
  onSelect: (ticker: string) => void;
  selectedTicker: string | null;
  compact?: boolean;
}

export function DealSearch({
  deals,
  isLoading,
  onSelect,
  selectedTicker,
  compact,
}: DealSearchProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filtered = deals?.filter(
    (d) =>
      d.ticker.toLowerCase().includes(query.toLowerCase()) ||
      d.trust_name.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div
      ref={wrapperRef}
      className={compact ? "relative w-64" : "relative w-full max-w-[400px]"}
    >
      <Input
        placeholder={
          isLoading
            ? "Loading deals…"
            : 'Search by deal ticker (e.g., BMARK 2024-V6)'
        }
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setOpen(false);
            (e.target as HTMLInputElement).blur();
          }
          if (e.key === "Enter" && filtered && filtered.length > 0) {
            onSelect(filtered[0].ticker);
            setQuery("");
            setOpen(false);
            (e.target as HTMLInputElement).blur();
          }
        }}
        className={`h-10 rounded-md border-zinc-200 text-sm ${compact ? "h-8" : ""}`}
      />
      {selectedTicker && !open && !query && (
        <span className="absolute right-2 top-2.5 text-xs text-muted-foreground font-mono">
          {selectedTicker}
        </span>
      )}
      {open && filtered && filtered.length > 0 && (
        <div className="absolute z-50 top-11 left-0 w-full bg-white border border-zinc-200 rounded-md shadow-md max-h-72 overflow-y-auto">
          {filtered.map((deal) => (
            <button
              key={deal.ticker}
              className="w-full text-left px-3 py-2 text-sm hover:bg-zinc-50 flex justify-between items-center gap-2"
              onClick={() => {
                onSelect(deal.ticker);
                setQuery("");
                setOpen(false);
              }}
            >
              <span className="font-mono font-medium text-foreground">
                {deal.ticker}
              </span>
              <span className="text-xs text-muted-foreground truncate">
                {deal.trust_name}
              </span>
            </button>
          ))}
        </div>
      )}
      {open && filtered && filtered.length === 0 && query && (
        <div className="absolute z-50 top-11 left-0 w-full bg-white border border-zinc-200 rounded-md shadow-md px-3 py-2 text-sm text-muted-foreground">
          No deals found
        </div>
      )}
    </div>
  );
}
