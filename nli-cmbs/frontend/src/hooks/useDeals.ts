import { useQuery } from "@tanstack/react-query";
import { fetchDeals, fetchDeal } from "@/lib/api";

export function useDeals() {
  return useQuery({
    queryKey: ["deals"],
    queryFn: fetchDeals,
  });
}

export function useDeal(ticker: string | null) {
  return useQuery({
    queryKey: ["deal", ticker],
    queryFn: () => fetchDeal(ticker!),
    enabled: !!ticker,
  });
}
