import { useCallback } from "react";
import { useSearchParams } from "react-router";

export type ViewMode = "monthly" | "ytd";
export type SortMode = "urgency" | "spending" | "name";

const VIEW_MODES = new Set<ViewMode>(["monthly", "ytd"]);
const SORT_MODES = new Set<SortMode>(["urgency", "spending", "name"]);

const DEFAULT_VIEW: ViewMode = "monthly";
const DEFAULT_SORT: SortMode = "urgency";

export function useBudgetFilters() {
  const [searchParams, setSearchParams] = useSearchParams();

  const rawView = searchParams.get("view");
  const viewMode: ViewMode =
    rawView && VIEW_MODES.has(rawView as ViewMode)
      ? (rawView as ViewMode)
      : DEFAULT_VIEW;

  const rawSort = searchParams.get("sort");
  const sortMode: SortMode =
    rawSort && SORT_MODES.has(rawSort as SortMode)
      ? (rawSort as SortMode)
      : DEFAULT_SORT;

  const setViewMode = useCallback(
    (v: ViewMode) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (v === DEFAULT_VIEW) next.delete("view");
          else next.set("view", v);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const setSortMode = useCallback(
    (s: SortMode) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (s === DEFAULT_SORT) next.delete("sort");
          else next.set("sort", s);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  return { viewMode, setViewMode, sortMode, setSortMode };
}
