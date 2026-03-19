import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchReport } from "@/lib/api";
import { useCallback, useState } from "react";

export function useReport(ticker: string | null) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const query = useQuery({
    queryKey: ["report", ticker],
    queryFn: () => fetchReport(ticker!, regenerating),
    enabled: !!ticker && enabled,
    staleTime: Infinity,
  });

  const generate = useCallback(() => {
    setRegenerating(false);
    setEnabled(true);
  }, []);

  const regenerate = useCallback(() => {
    setRegenerating(true);
    queryClient.removeQueries({ queryKey: ["report", ticker] });
    setEnabled(true);
  }, [queryClient, ticker]);

  return { ...query, enabled, generate, regenerate };
}
