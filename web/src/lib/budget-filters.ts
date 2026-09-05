import { useEnumParam } from "@/hooks/useEnumParam";
import { type PersonScope, usePersonScopeParam } from "@/lib/person-scope";

export type BudgetScope = PersonScope;
export type ViewMode = "monthly" | "ytd";
export type SortMode = "urgency" | "spending" | "name";

const VIEW_MODES = new Set<ViewMode>(["monthly", "ytd"]);
const SORT_MODES = new Set<SortMode>(["urgency", "spending", "name"]);

export function useBudgetFilters() {
  const [scope, setScope] = usePersonScopeParam();
  const [viewMode, setViewMode] = useEnumParam("view", VIEW_MODES, "monthly");
  const [sortMode, setSortMode] = useEnumParam("sort", SORT_MODES, "urgency");

  return { scope, setScope, viewMode, setViewMode, sortMode, setSortMode };
}
