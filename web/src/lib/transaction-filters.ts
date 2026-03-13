import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router";
import type { ReconciliationTransaction } from "@/lib/reconciliation";

export type SortField = "date" | "merchant" | "amount" | "group";
export type SortDir = "asc" | "desc";

export interface SortState {
  field: SortField;
  dir: SortDir;
}

export const DEFAULT_SORT: SortState = { field: "date", dir: "desc" };

export function cycleSortState(
  current: SortState,
  clicked: SortField,
): SortState {
  if (current.field !== clicked) {
    return { field: clicked, dir: clicked === "date" ? "desc" : "asc" };
  }
  if (current.dir === "asc") return { field: clicked, dir: "desc" };
  return DEFAULT_SORT;
}

interface FilterState {
  query: string;
  payers: string[];
  categories: string[];
  tags: string[];
  minAmount: number | null;
  maxAmount: number | null;
  sort: SortState;
}

function parseSort(raw: string | null): SortState {
  if (!raw) return DEFAULT_SORT;
  const parts = raw.split(":");
  const field = parts[0] as SortField;
  const dir = parts[1] as SortDir;
  if (
    ["date", "merchant", "amount", "group"].includes(field) &&
    ["asc", "desc"].includes(dir)
  ) {
    return { field, dir };
  }
  return DEFAULT_SORT;
}

function serializeSort(s: SortState): string | null {
  if (s.field === DEFAULT_SORT.field && s.dir === DEFAULT_SORT.dir) return null;
  return `${s.field}:${s.dir}`;
}

export function useTransactionFilters(
  transactions: ReconciliationTransaction[],
  categoryGroups: Map<string, string>,
) {
  const [searchParams, setSearchParams] = useSearchParams();

  const state: FilterState = useMemo(() => {
    const pParam = searchParams.getAll("payer");
    const cParam = searchParams.getAll("cat");
    const tParam = searchParams.getAll("tag");
    return {
      query: searchParams.get("q") ?? "",
      payers: pParam,
      categories: cParam,
      tags: tParam,
      minAmount: searchParams.get("minAmt")
        ? Number(searchParams.get("minAmt"))
        : null,
      maxAmount: searchParams.get("maxAmt")
        ? Number(searchParams.get("maxAmt"))
        : null,
      sort: parseSort(searchParams.get("sort")),
    };
  }, [searchParams]);

  const setFilter = useCallback(
    (updates: Partial<FilterState>) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if ("query" in updates) {
            if (updates.query) next.set("q", updates.query);
            else next.delete("q");
          }
          if ("payers" in updates) {
            next.delete("payer");
            for (const p of updates.payers ?? []) next.append("payer", p);
          }
          if ("categories" in updates) {
            next.delete("cat");
            for (const c of updates.categories ?? []) next.append("cat", c);
          }
          if ("tags" in updates) {
            next.delete("tag");
            for (const t of updates.tags ?? []) next.append("tag", t);
          }
          if ("minAmount" in updates) {
            if (updates.minAmount != null)
              next.set("minAmt", String(updates.minAmount));
            else next.delete("minAmt");
          }
          if ("maxAmount" in updates) {
            if (updates.maxAmount != null)
              next.set("maxAmt", String(updates.maxAmount));
            else next.delete("maxAmt");
          }
          if ("sort" in updates) {
            const s = serializeSort(updates.sort ?? DEFAULT_SORT);
            if (s) next.set("sort", s);
            else next.delete("sort");
          }
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const setQuery = useCallback(
    (q: string) => setFilter({ query: q }),
    [setFilter],
  );

  const setPayers = useCallback(
    (p: string[]) => setFilter({ payers: p }),
    [setFilter],
  );

  const setCategories = useCallback(
    (c: string[]) => setFilter({ categories: c }),
    [setFilter],
  );

  const setTags = useCallback(
    (t: string[]) => setFilter({ tags: t }),
    [setFilter],
  );

  const setAmountRange = useCallback(
    (min: number | null, max: number | null) =>
      setFilter({ minAmount: min, maxAmount: max }),
    [setFilter],
  );

  const setSort = useCallback(
    (s: SortState) => setFilter({ sort: s }),
    [setFilter],
  );

  const clearAll = useCallback(() => {
    setFilter({
      query: "",
      payers: [],
      categories: [],
      tags: [],
      minAmount: null,
      maxAmount: null,
      sort: DEFAULT_SORT,
    });
  }, [setFilter]);

  const availableTags = useMemo(() => {
    const tags = new Set<string>();
    for (const tx of transactions) {
      for (const t of tx.tags) tags.add(t);
    }
    return [...tags].sort();
  }, [transactions]);

  const filtered = useMemo(() => {
    let result = transactions;

    // Search
    if (state.query) {
      const q = state.query.toLowerCase();
      result = result.filter(
        (tx) =>
          tx.merchant.toLowerCase().includes(q) ||
          tx.category.toLowerCase().includes(q) ||
          tx.notes.toLowerCase().includes(q),
      );
    }

    // Payer filter (OR within group)
    if (state.payers.length > 0) {
      const payerSet = new Set(state.payers);
      result = result.filter((tx) => payerSet.has(tx.payer_person_id));
    }

    // Category filter (OR within group)
    if (state.categories.length > 0) {
      const catSet = new Set(state.categories);
      result = result.filter((tx) => catSet.has(tx.category));
    }

    // Tag filter (OR within group)
    if (state.tags.length > 0) {
      const tagSet = new Set(state.tags);
      result = result.filter((tx) => tx.tags.some((t) => tagSet.has(t)));
    }

    // Amount range (absolute value)
    const { minAmount, maxAmount } = state;
    if (minAmount != null) {
      result = result.filter((tx) => Math.abs(tx.amount) >= minAmount);
    }
    if (maxAmount != null) {
      result = result.filter((tx) => Math.abs(tx.amount) <= maxAmount);
    }

    // Sort
    return sortList(result, state.sort, categoryGroups);
  }, [transactions, state, categoryGroups]);

  const activeFilterCount =
    (state.query ? 1 : 0) +
    (state.payers.length > 0 ? 1 : 0) +
    (state.categories.length > 0 ? 1 : 0) +
    (state.tags.length > 0 ? 1 : 0) +
    (state.minAmount != null || state.maxAmount != null ? 1 : 0);

  return {
    filtered,
    totalCount: transactions.length,
    query: state.query,
    payers: state.payers,
    categories: state.categories,
    tags: state.tags,
    minAmount: state.minAmount,
    maxAmount: state.maxAmount,
    sort: state.sort,
    setQuery,
    setPayers,
    setCategories,
    setTags,
    setAmountRange,
    setSort,
    clearAll,
    activeFilterCount,
    availableTags,
  };
}

export type TransactionFilters = ReturnType<typeof useTransactionFilters>;

export function sortList(
  transactions: ReconciliationTransaction[],
  sort: SortState,
  categoryGroups: Map<string, string>,
): ReconciliationTransaction[] {
  const arr = [...transactions];
  const { field, dir } = sort;
  const mult = dir === "asc" ? 1 : -1;
  arr.sort((a, b) => {
    let cmp = 0;
    switch (field) {
      case "date":
        cmp =
          a.date.localeCompare(b.date) || a.merchant.localeCompare(b.merchant);
        break;
      case "merchant":
        cmp = a.merchant.localeCompare(b.merchant);
        break;
      case "amount":
        cmp = Math.abs(a.amount) - Math.abs(b.amount);
        break;
      case "group": {
        const ga = categoryGroups.get(a.category) ?? "Uncategorized";
        const gb = categoryGroups.get(b.category) ?? "Uncategorized";
        cmp = ga.localeCompare(gb);
        break;
      }
    }
    return cmp * mult;
  });
  return arr;
}
