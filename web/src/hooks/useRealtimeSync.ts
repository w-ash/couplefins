import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  getGetBudgetOverviewQueryKey,
  getGetBudgetsQueryKey,
} from "@/api/generated/budgets/budgets";
import { getGetDashboardQueryKey } from "@/api/generated/dashboard/dashboard";
import { getGetSpendingTrendsQueryKey } from "@/api/generated/insights/insights";
import { getGetReconciliationQueryKey } from "@/api/generated/reconciliation/reconciliation";
import { getGetSettleUpDataQueryKey } from "@/api/generated/settlements/settlements";
import { getGetTagsQueryKey } from "@/api/generated/transactions/transactions";

const ENTITY_QUERY_KEYS: Record<string, readonly (readonly unknown[])[]> = {
  settlements: [
    getGetSettleUpDataQueryKey(),
    getGetDashboardQueryKey(),
    getGetReconciliationQueryKey(),
  ],
  transactions: [
    getGetReconciliationQueryKey(),
    getGetDashboardQueryKey(),
    getGetTagsQueryKey(),
    getGetBudgetOverviewQueryKey(),
    getGetSpendingTrendsQueryKey(),
  ],
  uploads: [
    getGetDashboardQueryKey(),
    getGetReconciliationQueryKey(),
    getGetBudgetOverviewQueryKey(),
    getGetBudgetsQueryKey(),
    getGetSpendingTrendsQueryKey(),
  ],
  reconciliation: [
    getGetReconciliationQueryKey(),
    getGetSettleUpDataQueryKey(),
    getGetDashboardQueryKey(),
  ],
};

export function useRealtimeSync(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    const eventSource = new EventSource("/api/v1/events");

    eventSource.onmessage = (event: MessageEvent) => {
      try {
        const { entity } = JSON.parse(event.data as string) as {
          entity: string;
        };
        const queryKeys = ENTITY_QUERY_KEYS[entity];
        if (queryKeys) {
          for (const queryKey of queryKeys) {
            queryClient.invalidateQueries({ queryKey });
          }
        }
      } catch {
        // Ignore malformed events
      }
    };

    return () => {
      eventSource.close();
    };
  }, [queryClient]);
}
