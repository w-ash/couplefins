import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router";
import type { TransactionResponse } from "@/api/generated/model";

export const DISCUSS_TAG = "discuss";

export function hasDiscussTag(tx: TransactionResponse): boolean {
  return tx.tags.some((t) => t.toLowerCase() === DISCUSS_TAG);
}

// A non-household transaction is in the current user's Personal scope only
// when their share of the cost (derived from payer_percentage) is greater than
// zero. Falls back to !household when identity isn't yet hydrated.
export function isInPersonalScope(
  tx: TransactionResponse,
  currentPersonId: string | null,
): boolean {
  if (tx.household) return false;
  if (!currentPersonId) return true;
  const myShare =
    tx.payer_person_id === currentPersonId
      ? tx.payer_percentage
      : 100 - tx.payer_percentage;
  return myShare > 0;
}

// "Spotted" = I fronted cash for an expense that is entirely my partner's.
// Detected purely by payer fields (never by tags): I am the payer, my share is
// 0%, and it isn't a household expense. Returns false when identity isn't
// hydrated — there's no sensible default for an ownership-based scope.
//
// Note: the backend `get_reconciliation` use case (scope=all) returns
// `household ∪ {tx where current user is the payer}`, so this filter only
// surfaces "I spotted them"; rows where my partner spotted me (they paid, I
// owe 100%) are not in the dataset. Showing both directions requires a
// backend change.
export function isInSpottedScope(
  tx: TransactionResponse,
  currentPersonId: string | null,
): boolean {
  if (!currentPersonId) return false;
  if (tx.household) return false;
  return tx.payer_person_id === currentPersonId && tx.payer_percentage === 0;
}

export function isSettlementLinked(tx: TransactionResponse): boolean {
  return tx.is_settlement === true;
}

// Negated so expense-heavy sets render as a positive number.
export function sumNet(transactions: TransactionResponse[]): number {
  // `|| 0` collapses the `-0` produced by `-(0)` on an empty list.
  return -transactions.reduce((s, t) => s + t.amount, 0) || 0;
}

export type TransactionScope = "household" | "personal" | "spotted" | "all";

export const SCOPE_LABELS: Record<TransactionScope, string> = {
  all: "All",
  household: "Household",
  personal: "Personal",
  spotted: "Spotted",
};

const VALID_SCOPES = new Set<string>(
  Object.keys(SCOPE_LABELS) as TransactionScope[],
);

export interface BucketStat {
  count: number;
  amount: number;
}

export interface ReconciliationBuckets {
  total: BucketStat;
  household: BucketStat;
  householdRefunds: BucketStat;
  personal: BucketStat;
  personalSplit: BucketStat;
  spotted: BucketStat;
  partnerPaid: BucketStat;
  excluded: BucketStat;
}

function emptyStat(): BucketStat {
  return { count: 0, amount: 0 };
}

function add(stat: BucketStat, abs: number) {
  stat.count++;
  stat.amount += abs;
}

// Identity is required for the personal/spotted distinction; without it,
// non-household rows fall into `personal` defensively.
export function bucketTransactions(
  transactions: TransactionResponse[],
  currentPersonId: string | null,
): ReconciliationBuckets {
  const buckets: ReconciliationBuckets = {
    total: emptyStat(),
    household: emptyStat(),
    householdRefunds: emptyStat(),
    personal: emptyStat(),
    personalSplit: emptyStat(),
    spotted: emptyStat(),
    partnerPaid: emptyStat(),
    excluded: emptyStat(),
  };

  for (const tx of transactions) {
    const abs = Math.abs(tx.amount);
    add(buckets.total, abs);

    if (tx.is_excluded) {
      add(buckets.excluded, abs);
      continue;
    }

    if (tx.household) {
      add(buckets.household, abs);
      if (tx.amount > 0) add(buckets.householdRefunds, abs);
      continue;
    }

    const isMine =
      currentPersonId === null || tx.payer_person_id === currentPersonId;
    if (!isMine) {
      add(buckets.partnerPaid, abs);
      continue;
    }
    if (tx.payer_percentage === 0) {
      add(buckets.spotted, abs);
    } else {
      add(buckets.personal, abs);
      if (tx.payer_percentage < 100) add(buckets.personalSplit, abs);
    }
  }

  return buckets;
}

export interface ScopeCounts {
  all: number;
  household: number;
  personal: number;
  spotted: number;
}

export function computeScopeCounts(
  transactions: TransactionResponse[],
  currentPersonId: string | null,
): ScopeCounts {
  let household = 0;
  let personal = 0;
  let spotted = 0;
  for (const tx of transactions) {
    if (tx.household) household++;
    if (isInPersonalScope(tx, currentPersonId)) personal++;
    if (isInSpottedScope(tx, currentPersonId)) spotted++;
  }
  return { all: transactions.length, household, personal, spotted };
}

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
  scope: TransactionScope;
  query: string;
  payers: string[];
  categories: string[];
  tags: string[];
  minAmount: number | null;
  maxAmount: number | null;
  hasNotes: boolean;
  discuss: boolean;
  settlement: boolean;
  sort: SortState;
}

// URL param names this hook owns. Exported so cross-page links (e.g. the
// Settle Up audit table → Transactions) reference a single source of truth.
export const TX_FILTER_PARAMS = {
  scope: "scope",
  query: "q",
  payer: "payer",
  category: "cat",
  tag: "tag",
  minAmount: "minAmt",
  maxAmount: "maxAmt",
  hasNotes: "hasNotes",
  discuss: "discuss",
  settlement: "settlement",
  sort: "sort",
} as const;

const SORT_FIELDS: readonly SortField[] = [
  "date",
  "merchant",
  "amount",
  "group",
];
const SORT_DIRS: readonly SortDir[] = ["asc", "desc"];

function parseSort(raw: string | null): SortState {
  if (!raw) return DEFAULT_SORT;
  const [rawField, rawDir] = raw.split(":");
  const field = SORT_FIELDS.find((f) => f === rawField);
  const dir = SORT_DIRS.find((d) => d === rawDir);
  if (field && dir) return { field, dir };
  return DEFAULT_SORT;
}

function serializeSort(s: SortState): string | null {
  if (s.field === DEFAULT_SORT.field && s.dir === DEFAULT_SORT.dir) return null;
  return `${s.field}:${s.dir}`;
}

function parseScope(raw: string | null): TransactionScope {
  if (raw && VALID_SCOPES.has(raw)) return raw as TransactionScope;
  return "all";
}

export function useTransactionFilters(
  transactions: TransactionResponse[],
  categoryGroups: Map<string, string>,
  currentPersonId: string | null,
) {
  const [searchParams, setSearchParams] = useSearchParams();

  const state: FilterState = useMemo(() => {
    const minRaw = searchParams.get(TX_FILTER_PARAMS.minAmount);
    const maxRaw = searchParams.get(TX_FILTER_PARAMS.maxAmount);
    return {
      scope: parseScope(searchParams.get(TX_FILTER_PARAMS.scope)),
      query: searchParams.get(TX_FILTER_PARAMS.query) ?? "",
      payers: searchParams.getAll(TX_FILTER_PARAMS.payer),
      categories: searchParams.getAll(TX_FILTER_PARAMS.category),
      tags: searchParams.getAll(TX_FILTER_PARAMS.tag),
      minAmount: minRaw ? Number(minRaw) : null,
      maxAmount: maxRaw ? Number(maxRaw) : null,
      hasNotes: searchParams.get(TX_FILTER_PARAMS.hasNotes) === "1",
      discuss: searchParams.get(TX_FILTER_PARAMS.discuss) === "1",
      settlement: searchParams.get(TX_FILTER_PARAMS.settlement) === "1",
      sort: parseSort(searchParams.get(TX_FILTER_PARAMS.sort)),
    };
  }, [searchParams]);

  const setFilter = useCallback(
    (updates: Partial<FilterState>) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          const setStr = (k: string, v: string | null) =>
            v !== null ? next.set(k, v) : next.delete(k);
          const setMulti = (k: string, vs: readonly string[]) => {
            next.delete(k);
            for (const v of vs) next.append(k, v);
          };
          const setFlag = (k: string, v: boolean) => setStr(k, v ? "1" : null);
          const optStr = (v: string | null | undefined) => v || null;
          const optNum = (v: number | null | undefined) =>
            v != null ? String(v) : null;

          if ("scope" in updates) {
            const s = updates.scope;
            setStr(TX_FILTER_PARAMS.scope, !s || s === "all" ? null : s);
          }
          if ("query" in updates)
            setStr(TX_FILTER_PARAMS.query, optStr(updates.query));
          if ("payers" in updates)
            setMulti(TX_FILTER_PARAMS.payer, updates.payers ?? []);
          if ("categories" in updates)
            setMulti(TX_FILTER_PARAMS.category, updates.categories ?? []);
          if ("tags" in updates)
            setMulti(TX_FILTER_PARAMS.tag, updates.tags ?? []);
          if ("minAmount" in updates)
            setStr(TX_FILTER_PARAMS.minAmount, optNum(updates.minAmount));
          if ("maxAmount" in updates)
            setStr(TX_FILTER_PARAMS.maxAmount, optNum(updates.maxAmount));
          if ("hasNotes" in updates)
            setFlag(TX_FILTER_PARAMS.hasNotes, updates.hasNotes ?? false);
          if ("discuss" in updates)
            setFlag(TX_FILTER_PARAMS.discuss, updates.discuss ?? false);
          if ("settlement" in updates)
            setFlag(TX_FILTER_PARAMS.settlement, updates.settlement ?? false);
          if ("sort" in updates)
            setStr(
              TX_FILTER_PARAMS.sort,
              serializeSort(updates.sort ?? DEFAULT_SORT),
            );

          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const setScope = useCallback(
    (s: TransactionScope) => setFilter({ scope: s }),
    [setFilter],
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

  const setHasNotes = useCallback(
    (v: boolean) => setFilter({ hasNotes: v }),
    [setFilter],
  );

  const setDiscuss = useCallback(
    (v: boolean) => setFilter({ discuss: v }),
    [setFilter],
  );

  const setSettlement = useCallback(
    (v: boolean) => setFilter({ settlement: v }),
    [setFilter],
  );

  const setSort = useCallback(
    (s: SortState) => setFilter({ sort: s }),
    [setFilter],
  );

  const clearAll = useCallback(() => {
    setFilter({
      scope: "all",
      query: "",
      payers: [],
      categories: [],
      tags: [],
      minAmount: null,
      maxAmount: null,
      hasNotes: false,
      discuss: false,
      settlement: false,
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

    // Scope filter (household / personal / spotted)
    if (state.scope === "household") {
      result = result.filter((tx) => tx.household);
    } else if (state.scope === "personal") {
      result = result.filter((tx) => isInPersonalScope(tx, currentPersonId));
    } else if (state.scope === "spotted") {
      result = result.filter((tx) => isInSpottedScope(tx, currentPersonId));
    }

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

    // Notes / Discuss quick-filters
    if (state.hasNotes) {
      result = result.filter((tx) => tx.notes !== "");
    }
    if (state.discuss) {
      result = result.filter((tx) => hasDiscussTag(tx));
    }
    if (state.settlement) {
      result = result.filter((tx) => isSettlementLinked(tx));
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
  }, [transactions, state, categoryGroups, currentPersonId]);

  const { notesCount, discussCount, settlementCount } = useMemo(() => {
    let notes = 0;
    let discuss = 0;
    let settlement = 0;
    for (const tx of transactions) {
      if (tx.notes !== "") notes++;
      if (hasDiscussTag(tx)) discuss++;
      if (isSettlementLinked(tx)) settlement++;
    }
    return {
      notesCount: notes,
      discussCount: discuss,
      settlementCount: settlement,
    };
  }, [transactions]);

  const scopeCounts = useMemo(
    () => computeScopeCounts(transactions, currentPersonId),
    [transactions, currentPersonId],
  );

  const activeFilterCount =
    (state.scope !== "all" ? 1 : 0) +
    (state.query ? 1 : 0) +
    (state.payers.length > 0 ? 1 : 0) +
    (state.categories.length > 0 ? 1 : 0) +
    (state.tags.length > 0 ? 1 : 0) +
    (state.minAmount != null || state.maxAmount != null ? 1 : 0) +
    (state.hasNotes ? 1 : 0) +
    (state.discuss ? 1 : 0) +
    (state.settlement ? 1 : 0);

  return {
    filtered,
    totalCount: transactions.length,
    scope: state.scope,
    query: state.query,
    payers: state.payers,
    categories: state.categories,
    tags: state.tags,
    minAmount: state.minAmount,
    maxAmount: state.maxAmount,
    hasNotes: state.hasNotes,
    discuss: state.discuss,
    settlement: state.settlement,
    sort: state.sort,
    notesCount,
    discussCount,
    settlementCount,
    scopeCounts,
    setScope,
    setQuery,
    setPayers,
    setCategories,
    setTags,
    setAmountRange,
    setHasNotes,
    setDiscuss,
    setSettlement,
    setSort,
    clearAll,
    activeFilterCount,
    availableTags,
  };
}

export type TransactionFilters = ReturnType<typeof useTransactionFilters>;

export function sortList(
  transactions: TransactionResponse[],
  sort: SortState,
  categoryGroups: Map<string, string>,
): TransactionResponse[] {
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
