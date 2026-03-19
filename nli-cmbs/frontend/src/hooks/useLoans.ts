import { useQuery } from "@tanstack/react-query";
import { fetchLoans, fetchMaturityWall } from "@/lib/api";

export function useLoans(ticker: string | null) {
  return useQuery({
    queryKey: ["loans", ticker],
    queryFn: () => fetchLoans(ticker!),
    enabled: !!ticker,
  });
}

export function useMaturityWall(ticker: string | null) {
  return useQuery({
    queryKey: ["maturity-wall", ticker],
    queryFn: () => fetchMaturityWall(ticker!),
    enabled: !!ticker,
  });
}
