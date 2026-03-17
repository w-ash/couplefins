# Utilities & State Management Reference

## State Management

### URL-Driven State (primary pattern)

Filters, date ranges, view modes, and month navigation are all stored in URL search params — not React state or Zustand. This enables shareable URLs and browser back/forward.

Key hooks:
- `useMonthYear()` → `{ year, month }` from `?year=&month=` (`web/src/lib/format.ts`)
- `useDateRange()` → `{ startDate, endDate }` from URL params (`web/src/lib/date-range.ts`)
- `useBudgetFilters()` → `{ viewMode, sortMode }` from URL params (`web/src/lib/budget-filters.ts`)
- `useTransactionFilters()` → filters + sorted results (`web/src/lib/transaction-filters.ts`)

### Zustand (identity only)

- `useIdentityStore` — `currentPersonId` persisted to `localStorage` key `couplefins:currentPersonId` (`web/src/lib/identity.ts`)
- `useIdentityHydrated()` — Detects Zustand rehydration before rendering identity-dependent UI

### Tanstack Query (server state)

- All API calls via Orval-generated hooks in `web/src/api/generated/`
- Pattern: `const { data, isLoading, error } = useGetThing(params)`
- Response access: `data?.status === 200 ? data.data : undefined`
- Cache invalidation on mutations: `queryClient.invalidateQueries({ queryKey: getGetThingQueryKey(params) })`

## Data Fetching Pattern

```tsx
import { useGetBudgetOverview, getGetBudgetOverviewQueryKey } from "@/api/generated/budgets/budgets";

// Read
const params = useMemo(() => ({ year, month }), [year, month]);
const { data: response, isLoading, error, refetch } = useGetBudgetOverview(params);
const data = response?.status === 200 ? response.data : undefined;

// Mutate + invalidate
const queryClient = useQueryClient();
const mutation = usePostBudget({
  mutation: {
    onSuccess: () => queryClient.invalidateQueries({
      queryKey: getGetBudgetOverviewQueryKey(params),
    }),
  },
});
```

## Utility Module Reference

| Module | Key exports |
|---|---|
| `lib/format.ts` | `formatCurrency()`, `formatDate()`, `formatSplit()`, `plural()`, `buildSettlementLabel()`, `useMonthYear()`, `MONTHS` |
| `lib/input-styles.ts` | `baseInputClass`, `selectInputClass`, `triggerButtonClass`, `actionLinkClass`, `inputErrorClass` |
| `lib/theme.ts` | `getStoredTheme()`, `storeTheme()`, `resolveIsDark()`, `applyTheme()` |
| `lib/identity.ts` | `useIdentityStore`, `useIdentityHydrated()` |
| `lib/persons.ts` | `usePersonMaps()` → `personNames`, `getPersonName()`, `getPersonColor()` |
| `lib/categories.ts` | `useGroupIconMap()`, `useInvalidateCategories()` |
| `lib/category-icons.ts` | `getCategoryGroupIcon()`, `ICON_OPTIONS`, `CATEGORY_ICON_REGISTRY` |
| `lib/date-range.ts` | `monthStartEnd()`, `thisMonth()`, `lastMonth()`, `useDateRange()`, `formatRangeLabel()` |
| `lib/budget-filters.ts` | `useBudgetFilters()` → `viewMode`, `sortMode` |
| `lib/transaction-filters.ts` | `useTransactionFilters()` → filtered results + active filter count |
| `lib/adjustments.ts` | `downloadAdjustmentCsv()` |
| `hooks/useSetToggle.ts` | `useSetToggle()` → Set-based multi-select state |
| `hooks/useTemporary.ts` | `useTemporary()` → auto-resetting state (e.g., success messages) |
| `types/person.ts` | `getPersonAccentColor()`, `PERSON_ACCENT_COLORS` |
