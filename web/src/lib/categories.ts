import { useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { apiFetch } from "./api";

export interface CategoryGroup {
  id: string;
  name: string;
  categories: string[];
}

export const CATEGORY_GROUPS_QUERY_KEY = ["category-groups"] as const;
export const UNMAPPED_CATEGORIES_QUERY_KEY = ["unmapped-categories"] as const;

export function fetchCategoryGroups(): Promise<CategoryGroup[]> {
  return apiFetch("/api/v1/category-groups");
}

export function fetchUnmappedCategories(): Promise<string[]> {
  return apiFetch("/api/v1/category-mappings/unmapped");
}

export function createCategoryGroup(name: string): Promise<CategoryGroup> {
  return apiFetch("/api/v1/category-groups", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export function renameCategoryGroup(
  groupId: string,
  name: string,
): Promise<CategoryGroup> {
  return apiFetch(`/api/v1/category-groups/${groupId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export function deleteCategoryGroup(groupId: string): Promise<void> {
  return apiFetch(`/api/v1/category-groups/${groupId}`, {
    method: "DELETE",
  });
}

export function useInvalidateCategories() {
  const queryClient = useQueryClient();
  return useCallback(() => {
    queryClient.invalidateQueries({ queryKey: CATEGORY_GROUPS_QUERY_KEY });
    queryClient.invalidateQueries({
      queryKey: UNMAPPED_CATEGORIES_QUERY_KEY,
    });
  }, [queryClient]);
}

export function bulkUpdateMappings(
  mappings: { category: string; group_id: string }[],
): Promise<{ updated: number }> {
  return apiFetch("/api/v1/category-mappings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mappings }),
  });
}
