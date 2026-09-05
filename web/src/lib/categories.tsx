import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import {
  getGetCategoryGroupsQueryKey,
  getGetUnmappedCategoriesQueryKey,
  useGetCategoryGroups,
} from "@/api/generated/category-groups/category-groups";
import type { CategoryGroupResponse } from "@/api/generated/model";
import type { ComboboxOption } from "@/components/Combobox";
import { ENTITY_QUERY_KEYS } from "@/hooks/useRealtimeSync";
import { getCategoryGroupIcon } from "@/lib/category-icons";

export function useGroupIconMap(): Map<string, string | null> {
  const { data: response } = useGetCategoryGroups();
  const categoryGroups = response?.data;
  return useMemo(
    () => new Map((categoryGroups ?? []).map((g) => [g.id, g.icon])),
    [categoryGroups],
  );
}

export function useGroupOptions(
  groups: CategoryGroupResponse[],
): ComboboxOption[] {
  return useMemo(
    () =>
      groups.map((g) => {
        const Icon = getCategoryGroupIcon(g.icon);
        return {
          value: g.id,
          label: g.name,
          icon: <Icon className="size-4" />,
        };
      }),
    [groups],
  );
}

export function useInvalidateCategories() {
  const queryClient = useQueryClient();
  return useCallback(() => {
    for (const queryKey of [
      getGetCategoryGroupsQueryKey(),
      getGetUnmappedCategoriesQueryKey(),
      ...ENTITY_QUERY_KEYS.category_groups,
    ]) {
      queryClient.invalidateQueries({ queryKey });
    }
  }, [queryClient]);
}
