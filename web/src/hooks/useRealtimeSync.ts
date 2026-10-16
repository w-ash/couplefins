import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  getGetBudgetOverviewQueryKey,
  getGetBudgetsQueryKey,
} from "@/api/generated/budgets/budgets";
import { getGetDashboardQueryKey } from "@/api/generated/dashboard/dashboard";
import { getGetHouseQueryKey } from "@/api/generated/house/house";
import { getGetSpendingTrendsQueryKey } from "@/api/generated/insights/insights";
import { getGetReconciliationQueryKey } from "@/api/generated/reconciliation/reconciliation";
import { getGetAccountsQueryKey } from "@/api/generated/settings/settings";
import { getGetSettleUpDataQueryKey } from "@/api/generated/settlements/settlements";
import { getGetTagsQueryKey } from "@/api/generated/transactions/transactions";
import { subscribe } from "@/lib/event-source";

const TRANSACTION_QUERY_KEYS = [
  getGetReconciliationQueryKey(),
  getGetDashboardQueryKey(),
  getGetTagsQueryKey(),
  getGetBudgetOverviewQueryKey(),
  getGetSpendingTrendsQueryKey(),
] as const;

/** Queries a joint-account mark or unmark changes; also served by the SSE `accounts` event. */
export const ACCOUNT_QUERY_KEYS = [
  getGetAccountsQueryKey(),
  getGetReconciliationQueryKey(),
  getGetSettleUpDataQueryKey(),
  getGetHouseQueryKey(),
  getGetDashboardQueryKey(),
] as const;

export const ENTITY_QUERY_KEYS: Record<
  string,
  readonly (readonly unknown[])[]
> = {
  settlements: [
    getGetSettleUpDataQueryKey(),
    getGetDashboardQueryKey(),
    getGetReconciliationQueryKey(),
  ],
  transactions: TRANSACTION_QUERY_KEYS,
  // Mark or unmark moves rows in and out of settlement and budget.
  accounts: [...ACCOUNT_QUERY_KEYS, ...TRANSACTION_QUERY_KEYS],
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
  budgets: [getGetBudgetOverviewQueryKey(), getGetBudgetsQueryKey()],
  // A group's kind and a category's group feed the server-side spending and
  // settlement math, so every derived page refetches too. Served twice: by
  // the SSE "category_groups" event a partner's edit broadcasts, and by the
  // Settings page's own useInvalidateCategories after a local edit.
  category_groups: [
    getGetReconciliationQueryKey(),
    getGetDashboardQueryKey(),
    getGetBudgetOverviewQueryKey(),
    getGetSpendingTrendsQueryKey(),
    getGetSettleUpDataQueryKey(),
  ],
};

export function useRealtimeSync(): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    return subscribe((data) => {
      const entity = data.entity as string | undefined;
      if (!entity) return;
      const queryKeys = ENTITY_QUERY_KEYS[entity];
      if (queryKeys) {
        for (const queryKey of queryKeys) {
          queryClient.invalidateQueries({ queryKey });
        }
      }
    });
  }, [queryClient]);
}
