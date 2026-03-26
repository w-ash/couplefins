import { useEnumParam } from "@/hooks/useEnumParam";

export type BudgetScope = "household" | "personal";
export type ViewMode = "monthly" | "ytd";
export type SortMode = "urgency" | "spending" | "name";

const BUDGET_SCOPES = new Set<BudgetScope>(["household", "personal"]);
const VIEW_MODES = new Set<ViewMode>(["monthly", "ytd"]);
const SORT_MODES = new Set<SortMode>(["urgency", "spending", "name"]);

export function useBudgetFilters() {
  const [scope, setScope] = useEnumParam("scope", BUDGET_SCOPES, "household");
  const [viewMode, setViewMode] = useEnumParam("view", VIEW_MODES, "monthly");
  const [sortMode, setSortMode] = useEnumParam("sort", SORT_MODES, "urgency");

  return { scope, setScope, viewMode, setViewMode, sortMode, setSortMode };
}
