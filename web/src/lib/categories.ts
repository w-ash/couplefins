import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import {
  getGetCategoryGroupsQueryKey,
  getGetUnmappedCategoriesQueryKey,
  useGetCategoryGroups,
} from "@/api/generated/category-groups/category-groups";

export function useGroupIconMap(): Map<string, string | null> {
  const { data: response } = useGetCategoryGroups();
  const categoryGroups = response?.data;
  return useMemo(
    () => new Map((categoryGroups ?? []).map((g) => [g.id, g.icon])),
    [categoryGroups],
  );
}

export function useInvalidateCategories() {
  const queryClient = useQueryClient();
  return useCallback(() => {
    queryClient.invalidateQueries({
      queryKey: getGetCategoryGroupsQueryKey(),
    });
    queryClient.invalidateQueries({
      queryKey: getGetUnmappedCategoriesQueryKey(),
    });
  }, [queryClient]);
}
