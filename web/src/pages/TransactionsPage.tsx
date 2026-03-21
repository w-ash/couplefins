import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  Check,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Pencil,
  Upload,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { useGetCategoryGroups } from "@/api/generated/category-groups/category-groups";
import { getGetDashboardQueryKey } from "@/api/generated/dashboard/dashboard";
import type {
  BulkModifyTagsRequest,
  BulkUpdateRequest,
  CategoryGroupBreakdownResponse,
  ReconciliationResponse,
  TransactionResponse,
  UpdateTransactionRequest,
} from "@/api/generated/model";
import { useGetPersons } from "@/api/generated/persons/persons";
import {
  getGetReconciliationQueryKey,
  useGetReconciliation,
} from "@/api/generated/reconciliation/reconciliation";
import {
  getGetTagsQueryKey,
  useBulkModifyTags,
  useBulkUpdateTransactions,
  useGetTags,
  useUpdateTransaction,
} from "@/api/generated/transactions/transactions";
import { AdjustmentExportSection } from "@/components/AdjustmentExportSection";
import {
  type BulkChanges,
  BulkEditToolbar,
} from "@/components/BulkEditToolbar";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import type { ComboboxOption } from "@/components/Combobox";
import { DateRangePicker } from "@/components/DateRangePicker";
import { PageHeader } from "@/components/PageHeader";
import {
  EmptyStateActions,
  PageEmpty,
  PageError,
  PageLoading,
} from "@/components/PageStates";
import { PersonBadge } from "@/components/PersonBadge";
import { SegmentedControl } from "@/components/SegmentedControl";
import { StatsGrid } from "@/components/StatsGrid";
import { TransactionEditor } from "@/components/TransactionEditor";
import {
  ActiveFilterPills,
  AmountRangeFilter,
  CategoryFilter,
  PayerFilter,
  TagFilter,
} from "@/components/TransactionFilters";
import { TransactionSearch } from "@/components/TransactionSearch";
import { UnmappedCategoriesWarning } from "@/components/UnmappedCategoriesWarning";
import { UploadStatusRow } from "@/components/UploadStatusRow";
import { useSetToggle } from "@/hooks/useSetToggle";
import { useTemporary } from "@/hooks/useTemporary";
import { useGroupIconMap } from "@/lib/categories";
import { getCategoryGroupIcon } from "@/lib/category-icons";
import { formatRangeLabel, useDateRange } from "@/lib/date-range";
import {
  amountColorClass,
  computeShares,
  formatCurrency,
  formatDate,
  formatSplit,
  plural,
} from "@/lib/format";
import { PAGE_PADDING } from "@/lib/layout";
import { usePersonMaps } from "@/lib/persons";
import {
  ClassificationBadge,
  deriveTransactionType,
  TYPE_OPTIONS,
} from "@/lib/transaction-classification";
import type { SortField, SortState } from "@/lib/transaction-filters";
import {
  cycleSortState,
  type TypeFilter,
  useTransactionFilters,
} from "@/lib/transaction-filters";

function SummaryStats({
  data,
  getPersonName,
}: {
  data: ReconciliationResponse;
  getPersonName: (id: string) => string;
}) {
  const excludedCount = data.transactions.filter((tx) => tx.is_excluded).length;
  return (
    <StatsGrid
      stats={[
        {
          label: "Total shared",
          value: formatCurrency(data.net_shared_spending),
        },
        ...data.person_summaries.map((ps) => ({
          label: `${getPersonName(ps.person_id)} paid`,
          value: formatCurrency(ps.total_paid),
        })),
        ...(excludedCount > 0
          ? [{ label: "Excluded", value: String(excludedCount) }]
          : []),
      ]}
    />
  );
}

function CategoryGroupRow({
  group,
  icon,
}: {
  group: CategoryGroupBreakdownResponse;
  icon: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const Icon = getCategoryGroupIcon(icon);

  return (
    <>
      <tr
        className="border-b border-border-muted cursor-pointer hover:bg-muted/50"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="py-2.5 pr-4">
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${group.group_name}`}
            className="flex items-center gap-1.5 text-sm font-medium text-foreground"
          >
            {expanded ? (
              <ChevronDown className="size-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="size-4 text-muted-foreground" />
            )}
            <Icon className="size-4 text-muted-foreground" />
            {group.group_name}
          </button>
        </td>
        <td className="py-2.5 pr-4 text-right text-sm tabular-nums text-foreground">
          {formatCurrency(group.total_amount)}
        </td>
        <td className="py-2.5 text-right text-sm tabular-nums text-muted-foreground">
          {group.transaction_count}
        </td>
      </tr>
      {expanded &&
        group.categories.map((cat) => (
          <tr key={cat.category} className="border-b border-border-muted">
            <td className="py-1.5 pl-8 pr-4 text-sm text-muted-foreground">
              {cat.category}
            </td>
            <td className="py-1.5 pr-4 text-right text-sm tabular-nums text-muted-foreground">
              {formatCurrency(cat.total_amount)}
            </td>
            <td className="py-1.5 text-right text-sm tabular-nums text-muted-foreground">
              {cat.transaction_count}
            </td>
          </tr>
        ))}
    </>
  );
}

function CategoryGroupBreakdownTable({
  breakdowns,
  hasRefunds,
  groupIconMap,
}: {
  breakdowns: CategoryGroupBreakdownResponse[];
  hasRefunds: boolean;
  groupIconMap: Map<string, string | null>;
}) {
  if (breakdowns.length === 0) return null;

  return (
    <Card>
      <h2 className="mb-4 font-medium text-lg text-foreground">
        Category Breakdown
        {hasRefunds && (
          <span className="ml-2 text-xs font-normal text-muted-foreground">
            includes refunds
          </span>
        )}
      </h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="pb-2 pr-4 font-medium">Group</th>
            <th className="pb-2 pr-4 text-right font-medium">Total</th>
            <th className="pb-2 text-right font-medium">Txns</th>
          </tr>
        </thead>
        <tbody>
          {breakdowns.map((group) => (
            <CategoryGroupRow
              key={group.group_id ?? "uncategorized"}
              group={group}
              icon={
                group.group_id
                  ? (groupIconMap.get(group.group_id) ?? null)
                  : null
              }
            />
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function buildCategoryGroupLookup(
  breakdowns: CategoryGroupBreakdownResponse[],
): Map<string, string> {
  const lookup = new Map<string, string>();
  for (const group of breakdowns) {
    for (const cat of group.categories) {
      lookup.set(cat.category, group.group_name);
    }
  }
  return lookup;
}

function SortIndicator({ field, sort }: { field: SortField; sort: SortState }) {
  if (sort.field !== field) return null;
  return sort.dir === "asc" ? (
    <ChevronUp className="ml-0.5 inline size-3.5" />
  ) : (
    <ChevronDown className="ml-0.5 inline size-3.5" />
  );
}

function SortableHeader({
  field,
  sort,
  onSort,
  align,
  title,
  children,
  className: extraClassName,
}: {
  field: SortField;
  sort: SortState;
  onSort: (s: SortState) => void;
  align?: "right";
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th
      className={`pb-2 pr-4 font-medium cursor-pointer select-none transition-colors hover:text-foreground ${align === "right" ? "text-right" : ""} ${extraClassName ?? ""}`}
      title={title}
      onClick={() => onSort(cycleSortState(sort, field))}
    >
      {children}
      <SortIndicator field={field} sort={sort} />
    </th>
  );
}

interface BulkResult {
  message: string;
}

function TransactionTable({
  transactions,
  personNames,
  personEntries,
  getPersonColor,
  categoryGroups,
  categoryOptions,
  availableTags,
  tagOptions,
  isFinalized,
  sort,
  onSort,
  onBulkUpdate,
  onBulkTags,
  onTransactionUpdate,
  isSaving,
}: {
  transactions: TransactionResponse[];
  personNames: Map<string, string>;
  personEntries: Array<{ id: string; name: string }>;
  getPersonColor: (id: string) => string;
  categoryGroups: Map<string, string>;
  categoryOptions: ComboboxOption[];
  availableTags: string[];
  tagOptions: ComboboxOption[];
  isFinalized: boolean;
  sort: SortState;
  onSort: (s: SortState) => void;
  onBulkUpdate: (payload: BulkUpdateRequest) => Promise<unknown>;
  onBulkTags: (payload: BulkModifyTagsRequest) => Promise<unknown>;
  onTransactionUpdate: (id: string, fields: UpdateTransactionRequest) => void;
  isSaving: boolean;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [savedId, setSavedId] = useTemporary<string | null>(null);
  const [bulkMode, setBulkMode] = useState(false);
  const {
    selected,
    toggle: toggleSelected,
    setAll,
    clear: clearSelection,
  } = useSetToggle();

  const exitBulkMode = useCallback(() => {
    setBulkMode(false);
    clearSelection();
  }, [clearSelection]);

  const [bulkResult, setBulkResult] = useTemporary<BulkResult | null>(
    null,
    2000,
    exitBulkMode,
  );

  const colCount = 8 + personEntries.length + (bulkMode ? 1 : 0);

  const toggleAll = useCallback(() => {
    if (selected.size === transactions.length) clearSelection();
    else setAll(transactions.map((tx) => tx.id));
  }, [selected.size, transactions, clearSelection, setAll]);

  const selectedTagCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const tx of transactions) {
      if (!selected.has(tx.id)) continue;
      for (const tag of tx.tags) {
        counts.set(tag, (counts.get(tag) ?? 0) + 1);
      }
    }
    return counts;
  }, [transactions, selected]);

  const handleBulkApply = useCallback(
    async (ids: string[], changes: BulkChanges) => {
      const promises: Promise<unknown>[] = [];
      if (changes.payer_percentage != null || changes.category != null) {
        const payload: BulkUpdateRequest = { transaction_ids: ids };
        if (changes.payer_percentage != null)
          payload.payer_percentage = changes.payer_percentage;
        if (changes.category != null) payload.category = changes.category;
        promises.push(onBulkUpdate(payload));
      }
      if (changes.tags) {
        promises.push(
          onBulkTags({
            transaction_ids: ids,
            action: changes.tags.action,
            tags: changes.tags.tags,
          }),
        );
      }

      await Promise.all(promises);

      const parts: string[] = [];
      if (changes.payer_percentage != null) parts.push("split");
      if (changes.category != null) parts.push("category");
      if (changes.tags) parts.push("tags");
      setBulkResult({
        message: `Updated ${parts.join(", ")} on ${plural("transaction", ids.length)}`,
      });
    },
    [onBulkUpdate, onBulkTags, setBulkResult],
  );

  if (transactions.length === 0) return null;

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-medium text-lg text-foreground">Transactions</h2>
        {!isFinalized && !bulkMode && (
          <Button
            variant="secondary"
            size="sm"
            icon={<Pencil className="size-3.5" />}
            onClick={() => setBulkMode(true)}
          >
            Bulk Edit
          </Button>
        )}
      </div>

      {bulkMode && (
        <div className="mb-4">
          {bulkResult ? (
            <div
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3 shadow-sm"
              aria-live="polite"
            >
              <Check className="size-4 text-positive" />
              <span className="text-sm font-medium text-foreground">
                {bulkResult.message}
              </span>
            </div>
          ) : (
            <BulkEditToolbar
              selectedIds={selected}
              totalCount={transactions.length}
              selectedTagCounts={selectedTagCounts}
              categoryOptions={categoryOptions}
              availableTags={availableTags}
              saving={isSaving}
              onApply={handleBulkApply}
              onCancel={exitBulkMode}
            />
          )}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              {bulkMode && (
                <th className="w-8 pb-2 pr-2 align-middle">
                  <input
                    type="checkbox"
                    checked={
                      selected.size === transactions.length &&
                      transactions.length > 0
                    }
                    onChange={toggleAll}
                    className="size-4 accent-primary"
                  />
                </th>
              )}
              <SortableHeader field="date" sort={sort} onSort={onSort}>
                Date
              </SortableHeader>
              <SortableHeader field="merchant" sort={sort} onSort={onSort}>
                Merchant
              </SortableHeader>
              <th className="hidden pb-2 pr-4 font-medium sm:table-cell">
                Category
              </th>
              <SortableHeader
                field="group"
                sort={sort}
                onSort={onSort}
                className="hidden sm:table-cell"
              >
                Group
              </SortableHeader>
              <th className="hidden pb-2 pr-4 font-medium sm:table-cell">
                Paid by
              </th>
              <th className="hidden pb-2 pr-4 font-medium sm:table-cell">
                Type
              </th>
              <SortableHeader
                field="amount"
                sort={sort}
                onSort={onSort}
                align="right"
              >
                Amount
              </SortableHeader>
              <th
                className="hidden pb-2 pr-4 text-right font-medium sm:table-cell"
                title="How the expense is divided between you"
              >
                Split
              </th>
              {personEntries.map((p) => (
                <th
                  key={p.id}
                  className="hidden pb-2 text-right font-medium sm:table-cell"
                >
                  {p.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx) => {
              const isExpanded = expandedId === tx.id;
              return (
                <TransactionRow
                  key={tx.id}
                  tx={tx}
                  personNames={personNames}
                  getPersonColor={getPersonColor}
                  categoryGroups={categoryGroups}
                  categoryOptions={categoryOptions}
                  tagOptions={tagOptions}
                  personEntries={personEntries}
                  isExpanded={isExpanded}
                  isSaved={savedId === tx.id}
                  canEdit={!isFinalized && !bulkMode}
                  bulkMode={bulkMode}
                  isSelected={selected.has(tx.id)}
                  isSaving={isSaving}
                  colCount={colCount}
                  onToggleExpand={() =>
                    setExpandedId(isExpanded ? null : tx.id)
                  }
                  onToggleSelect={() => toggleSelected(tx.id)}
                  onTransactionUpdate={(fields) => {
                    onTransactionUpdate(tx.id, fields);
                    setSavedId(tx.id);
                    setExpandedId(null);
                  }}
                  onCancel={() => setExpandedId(null)}
                />
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function TransactionRow({
  tx,
  personNames,
  getPersonColor,
  categoryGroups,
  categoryOptions,
  tagOptions,
  personEntries,
  isExpanded,
  isSaved,
  canEdit,
  bulkMode,
  isSelected,
  isSaving,
  colCount,
  onToggleExpand,
  onToggleSelect,
  onTransactionUpdate,
  onCancel,
}: {
  tx: TransactionResponse;
  personNames: Map<string, string>;
  getPersonColor: (id: string) => string;
  categoryGroups: Map<string, string>;
  categoryOptions: ComboboxOption[];
  tagOptions: ComboboxOption[];
  personEntries: Array<{ id: string; name: string }>;
  isExpanded: boolean;
  isSaved: boolean;
  canEdit: boolean;
  bulkMode: boolean;
  isSelected: boolean;
  isSaving: boolean;
  colCount: number;
  onToggleExpand: () => void;
  onToggleSelect: () => void;
  onTransactionUpdate: (fields: UpdateTransactionRequest) => void;
  onCancel: () => void;
}) {
  const payerPct = tx.payer_percentage ?? 50;
  const { payerShare, otherShare } = computeShares(
    Math.abs(tx.amount),
    payerPct,
  );
  const payerName = personNames.get(tx.payer_person_id) ?? "Unknown";
  const payerColor = getPersonColor(tx.payer_person_id);
  const otherName =
    [...personNames].find(([id]) => id !== tx.payer_person_id)?.[1] ?? "Other";
  const categoryGroup = categoryGroups.get(tx.category) ?? "Uncategorized";
  const strikethrough = tx.is_excluded ? "line-through" : "";
  const txType = deriveTransactionType(tx.household, tx.payer_percentage);
  return (
    <>
      <tr
        className={`border-b border-border-muted transition-colors duration-300 ${canEdit ? "cursor-pointer hover:bg-muted/50" : ""} ${isExpanded ? "bg-muted/30" : ""} ${isSaved ? "bg-positive/10" : ""} ${tx.is_excluded ? "opacity-50" : ""}`}
        onClick={canEdit ? onToggleExpand : undefined}
      >
        {bulkMode && (
          <td className="py-2 pr-2 align-middle">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={onToggleSelect}
              onClick={(e) => e.stopPropagation()}
              className="size-4 accent-primary"
            />
          </td>
        )}
        <td
          className={`py-2 pr-4 text-muted-foreground tabular-nums ${strikethrough}`}
        >
          {formatDate(tx.date)}
        </td>
        <td className={`py-2 pr-4 text-foreground ${strikethrough}`}>
          <span className="flex items-center gap-1.5">
            {tx.merchant}
            {isSaved && <Check className="size-3.5 text-positive" />}
            <span className="sm:hidden">
              <ClassificationBadge type={txType} otherPersonName={otherName} />
            </span>
          </span>
        </td>
        <td
          className={`hidden py-2 pr-4 text-muted-foreground sm:table-cell ${strikethrough}`}
        >
          {tx.category}
        </td>
        <td className="hidden py-2 pr-4 text-muted-foreground sm:table-cell">
          {categoryGroup}
        </td>
        <td className="hidden py-2 pr-4 sm:table-cell">
          <PersonBadge name={payerName} accentColor={payerColor} size="xs" />
        </td>
        <td className="hidden py-2 pr-4 sm:table-cell">
          <ClassificationBadge type={txType} otherPersonName={otherName} />
        </td>
        <td
          className={`py-2 pr-4 text-right tabular-nums ${amountColorClass(tx.amount)}`}
        >
          {formatCurrency(tx.amount)}
        </td>
        <td className="hidden py-2 pr-4 text-right text-muted-foreground tabular-nums sm:table-cell">
          {formatSplit(tx.payer_percentage)}
        </td>
        {personEntries.map((p) => (
          <td
            key={p.id}
            className="hidden py-2 text-right text-muted-foreground tabular-nums sm:table-cell"
          >
            {formatCurrency(
              p.id === tx.payer_person_id ? payerShare : otherShare,
            )}
          </td>
        ))}
      </tr>
      {isExpanded && (
        <tr className="border-b border-border-muted bg-muted/30">
          <td colSpan={colCount} className="px-4">
            <div className="editor-enter">
              <TransactionEditor
                tx={tx}
                payerName={payerName}
                otherName={otherName}
                categoryOptions={categoryOptions}
                tagOptions={tagOptions}
                saving={isSaving}
                onSave={onTransactionUpdate}
                onCancel={onCancel}
              />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function TransactionsPage() {
  const { startDate, endDate, setDateRange, singleMonth } = useDateRange();
  const queryClient = useQueryClient();

  const { data: personsResponse } = useGetPersons();
  const persons = personsResponse?.data;

  const { data: categoryGroupsResponse } = useGetCategoryGroups();
  const categoryGroups = categoryGroupsResponse?.data;

  const { data: tagsResponse } = useGetTags();
  const availableTags = tagsResponse?.data ?? [];

  const reconciliationParams = useMemo(
    () => ({ start_date: startDate, end_date: endDate }),
    [startDate, endDate],
  );
  const {
    data: reconciliationResponse,
    isLoading,
    error,
    refetch,
  } = useGetReconciliation(reconciliationParams);
  const data =
    reconciliationResponse?.status === 200
      ? reconciliationResponse.data
      : undefined;

  const invalidateReconciliation = useCallback(() => {
    queryClient.invalidateQueries({
      queryKey: getGetReconciliationQueryKey(reconciliationParams),
    });
    queryClient.invalidateQueries({ queryKey: getGetDashboardQueryKey() });
    queryClient.invalidateQueries({ queryKey: getGetTagsQueryKey() });
  }, [queryClient, reconciliationParams]);

  const editMutation = useUpdateTransaction({
    mutation: { onSuccess: invalidateReconciliation },
  });

  const bulkUpdateMutation = useBulkUpdateTransactions({
    mutation: { onSuccess: invalidateReconciliation },
  });

  const bulkTagsMutation = useBulkModifyTags({
    mutation: { onSuccess: invalidateReconciliation },
  });

  const { personNames, getPersonName, getPersonColor } = usePersonMaps(persons);
  const categoryGroupLookup = useMemo(
    () =>
      data
        ? buildCategoryGroupLookup(data.category_group_breakdowns)
        : new Map<string, string>(),
    [data],
  );
  const groupIconMap = useGroupIconMap();

  const categoryOptions: ComboboxOption[] = useMemo(
    () =>
      (categoryGroups ?? []).flatMap((g) =>
        g.categories.map((cat) => ({
          value: cat.name,
          label: cat.name,
          group: g.name,
        })),
      ),
    [categoryGroups],
  );

  const tagOptions: ComboboxOption[] = useMemo(
    () => availableTags.map((t) => ({ value: t, label: t })),
    [availableTags],
  );

  const personEntries = useMemo(
    () => [...personNames].map(([id, name]) => ({ id, name })),
    [personNames],
  );

  const filters = useTransactionFilters(
    data?.transactions ?? [],
    categoryGroupLookup,
  );

  const periodLabel = formatRangeLabel(startDate, endDate);
  const isFinalized = data?.is_finalized === true;

  return (
    <div className={`mx-auto max-w-4xl ${PAGE_PADDING}`}>
      <PageHeader
        icon={<ArrowLeftRight className="size-6" />}
        title="Transactions"
      >
        <DateRangePicker
          startDate={startDate}
          endDate={endDate}
          setDateRange={setDateRange}
        />
      </PageHeader>

      {isLoading && <PageLoading label="Loading transactions..." />}

      {error && <PageError error={error} onRetry={() => refetch()} />}

      {data && (
        <div className="space-y-6">
          <UploadStatusRow
            statuses={data.upload_statuses}
            getPersonColor={getPersonColor}
          />

          {data.transaction_count === 0 ? (
            <PageEmpty
              icon={<Upload />}
              heading={`No shared transactions for ${periodLabel}`}
              description="Upload a CSV to see transactions."
              action={
                <EmptyStateActions
                  latestMonth={
                    singleMonth ? data.latest_transaction_month : null
                  }
                  currentYear={singleMonth?.year ?? 0}
                  currentMonth={singleMonth?.month ?? 0}
                  viewPath="transactions"
                />
              }
            />
          ) : (
            <>
              <SummaryStats data={data} getPersonName={getPersonName} />
              <CategoryGroupBreakdownTable
                breakdowns={data.category_group_breakdowns}
                hasRefunds={data.total_shared_refunds > 0}
                groupIconMap={groupIconMap}
              />
              {singleMonth && (
                <AdjustmentExportSection
                  persons={persons ?? []}
                  year={singleMonth.year}
                  month={singleMonth.month}
                />
              )}

              <TransactionSearch
                value={filters.query}
                onChange={filters.setQuery}
                filteredCount={filters.filtered.length}
                totalCount={filters.totalCount}
              />

              <div className="w-full overflow-x-auto sm:w-auto sm:overflow-visible">
                <SegmentedControl<TypeFilter>
                  options={[
                    { value: "all" as const, label: "All" },
                    ...TYPE_OPTIONS,
                    { value: "excluded" as const, label: "Excluded" },
                  ]}
                  value={filters.type}
                  onChange={filters.setType}
                  size="sm"
                  shape="pill"
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <PayerFilter
                  persons={personEntries}
                  activePayers={filters.payers}
                  onChange={filters.setPayers}
                />
                <CategoryFilter
                  breakdowns={data.category_group_breakdowns}
                  activeCategories={filters.categories}
                  onChange={filters.setCategories}
                />
                <TagFilter
                  availableTags={filters.availableTags}
                  activeTags={filters.tags}
                  onChange={filters.setTags}
                />
                <AmountRangeFilter
                  minAmount={filters.minAmount}
                  maxAmount={filters.maxAmount}
                  onChange={filters.setAmountRange}
                />
              </div>

              <ActiveFilterPills filters={filters} personNames={personNames} />

              <TransactionTable
                transactions={filters.filtered}
                personNames={personNames}
                personEntries={personEntries}
                getPersonColor={getPersonColor}
                categoryGroups={categoryGroupLookup}
                categoryOptions={categoryOptions}
                availableTags={availableTags}
                tagOptions={tagOptions}
                isFinalized={isFinalized}
                sort={filters.sort}
                onSort={filters.setSort}
                onBulkUpdate={(payload) =>
                  bulkUpdateMutation.mutateAsync({ data: payload })
                }
                onBulkTags={(payload) =>
                  bulkTagsMutation.mutateAsync({ data: payload })
                }
                onTransactionUpdate={(id, fields) =>
                  editMutation.mutate({ transactionId: id, data: fields })
                }
                isSaving={
                  editMutation.isPending ||
                  bulkUpdateMutation.isPending ||
                  bulkTagsMutation.isPending
                }
              />
              <UnmappedCategoriesWarning
                categories={data.unmapped_categories}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}
