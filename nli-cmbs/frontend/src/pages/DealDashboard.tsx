import { useState } from "react";
import { DealHeader } from "@/components/DealHeader";
import { OverviewTab } from "@/components/tabs/OverviewTab";
import { PropertyTab } from "@/components/tabs/PropertyTab";
import { CreditTab } from "@/components/tabs/CreditTab";
import { MaturitiesTab } from "@/components/tabs/MaturitiesTab";
import { LoansTab } from "@/components/tabs/LoansTab";
import type { DealDetail, Loan } from "@/lib/types";

const TABS = ["Overview", "Property", "Credit", "Maturities", "Loans"] as const;
type Tab = (typeof TABS)[number];

interface DealDashboardProps {
  deal: DealDetail;
  loans: Loan[];
  loansLoading: boolean;
  ticker: string;
}

export function DealDashboard({
  deal,
  loans,
  loansLoading,
  ticker,
}: DealDashboardProps) {
  const [activeTab, setActiveTab] = useState<Tab>("Overview");

  return (
    <div className="space-y-3">
      <DealHeader deal={deal} />

      {/* Tab navigation */}
      <div className="border-b border-zinc-200">
        <nav className="flex gap-0 -mb-px">
          {TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? "border-zinc-900 text-zinc-900"
                  : "border-transparent text-zinc-500 hover:text-zinc-700 hover:border-zinc-300"
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {loansLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 bg-zinc-100 rounded-md animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {activeTab === "Overview" && (
            <OverviewTab deal={deal} loans={loans} ticker={ticker} />
          )}
          {activeTab === "Property" && <PropertyTab loans={loans} />}
          {activeTab === "Credit" && <CreditTab loans={loans} />}
          {activeTab === "Maturities" && <MaturitiesTab loans={loans} />}
          {activeTab === "Loans" && <LoansTab loans={loans} />}
        </>
      )}
    </div>
  );
}
