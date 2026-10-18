import { useQueryClient } from "@tanstack/react-query";
import { HOUSE_QUERY_KEYS } from "@/hooks/useRealtimeSync";

/** Returns a function that refetches every query a House write changes. */
export function useInvalidateHouse(): () => void {
  const queryClient = useQueryClient();
  return () => {
    for (const queryKey of HOUSE_QUERY_KEYS) {
      queryClient.invalidateQueries({ queryKey });
    }
  };
}
