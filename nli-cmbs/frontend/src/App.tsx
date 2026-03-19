import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { DealSearch } from "@/components/search/DealSearch";
import { DealDashboard } from "@/pages/DealDashboard";
import { useDeals, useDeal } from "@/hooks/useDeals";
import { useLoans } from "@/hooks/useLoans";

function getTickerFromUrl(): string | null {
  // Support both ?deal=TICKER and /deals/TICKER
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("deal");
  if (fromQuery) return fromQuery;

  const match = window.location.pathname.match(/\/deals\/([^/]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function SkeletonDashboard() {
  return (
    <div className="space-y-3">
      <div className="h-8 w-64 bg-zinc-100 rounded animate-pulse" />
      <div className="h-6 w-96 bg-zinc-50 rounded animate-pulse" />
      <div className="grid grid-cols-4 gap-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="border border-zinc-200 rounded-md p-3">
            <div className="h-3 w-16 bg-zinc-100 rounded animate-pulse mb-2" />
            <div className="h-6 w-24 bg-zinc-100 rounded animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}

function App() {
  const [selectedTicker, setSelectedTicker] = useState<string | null>(
    getTickerFromUrl
  );
  const { data: deals, isLoading: dealsLoading } = useDeals();
  const {
    data: deal,
    isLoading: dealLoading,
    error: dealError,
  } = useDeal(selectedTicker);
  const { data: loans, isLoading: loansLoading } = useLoans(selectedTicker);

  useEffect(() => {
    document.title = deal ? `${deal.ticker} | NLI-CMBS` : "NLI-CMBS";
  }, [deal]);

  useEffect(() => {
    const handler = () => setSelectedTicker(getTickerFromUrl());
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, []);

  const handleSelect = useCallback((ticker: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set("deal", ticker);
    window.history.pushState({}, "", url.toString());
    setSelectedTicker(ticker);
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Header
        showSearch={!!selectedTicker}
        deals={deals}
        dealsLoading={dealsLoading}
        selectedTicker={selectedTicker}
        onSelect={handleSelect}
      />
      <main className="flex-1 w-full max-w-[1400px] mx-auto px-4 py-3">
        {!selectedTicker && (
          <div className="flex flex-col items-center justify-center py-32 gap-4">
            <DealSearch
              deals={deals}
              isLoading={dealsLoading}
              onSelect={handleSelect}
              selectedTicker={selectedTicker}
            />
            <p className="text-sm text-muted-foreground">
              CMBS Portfolio Intelligence — Search a deal to begin
            </p>
          </div>
        )}

        {selectedTicker && dealError && (
          <div className="border border-rose-200 bg-rose-50 rounded-md px-4 py-3 text-sm text-rose-700">
            Deal not found. Try another ticker.
          </div>
        )}

        {selectedTicker && dealLoading && <SkeletonDashboard />}

        {deal && (
          <DealDashboard
            deal={deal}
            loans={loans ?? []}
            loansLoading={loansLoading}
            ticker={selectedTicker!}
          />
        )}
      </main>
      <Footer />
    </div>
  );
}

export default App;
