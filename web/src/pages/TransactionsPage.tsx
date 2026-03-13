import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeftRight,
  ChevronDown,
  ChevronRight,
  Loader2,
  Pencil,
  Upload,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router";
import { AdjustmentExportSection } from "@/components/AdjustmentExportSection";
import { Button } from "@/components/Button";
import { FinalizationBanner } from "@/components/FinalizationBanner";
import { MonthSelector } from "@/components/MonthSelector";
import { BulkSplitEditor } from "@/components/SplitEditor";
import { TransactionEditor } from "@/components/TransactionEditor";
import { UnmappedCategoriesWarning } from "@/components/UnmappedCategoriesWarning";
import { DASHBOARD_QUERY_KEY } from "@/lib/dashboard";
import {
  computeShares,
  formatCurrency,
  formatDate,
  formatSplit,
  MONTHS,
  useMonthYear,
} from "@/lib/format";
import type {
  CategoryGroupBreakdown,
  ReconciliationData,
  ReconciliationTransaction,
} from "@/lib/reconciliation";
import {
  fetchReconciliation,
  finalizePeriod,
  unfinalizePeriod,
} from "@/lib/reconciliation";
import type { TransactionUpdateFields } from "@/lib/transactions";
import { updateTransaction, updateTransactionSplits } from "@/lib/transactions";
import {
  fetchPersons,
  getPersonAccentColor,
  PERSONS_QUERY_KEY,
} from "@/types/person";

function UploadStatusBanner({
  statuses,
}: {
  statuses: ReconciliationData["upload_statuses"];
}) {
  const missing = statuses.filter((s) => !s.has_uploaded);
  if (missing.length === 0) return null;

  return (
    <div className="flex items-start gap-2 rounded-lg border border-warning-border bg-warning-muted p-3">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
      <p className="text-sm text-warning-muted-foreground">
        {missing.map((s) => s.person_name).join(" and ")}{" "}
        {missing.length === 1 ? "hasn't" : "haven't"} uploaded yet this month.
      </p>
    </div>
  );
}

function SettlementCard({
  data,
  personNames,
  personIndexMap,
}: {
  data: ReconciliationData;
  personNames: Map<string, string>;
  personIndexMap: Map<string, number>;
}) {
  const { settlement } = data;
  if (!settlement) return null;

  const fromName = personNames.get(settlement.from_person_id) ?? "Unknown";
  const toName = personNames.get(settlement.to_person_id) ?? "Unknown";
  const fromColor = getPersonAccentColor(
    personIndexMap.get(settlement.from_person_id) ?? -1,
  );

  const isSettled = settlement.amount === 0;

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
      <p className="text-center text-2xl font-semibold text-foreground">
        {isSettled ? (
          "All settled!"
        ) : (
          <>
            <span
              className={`inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-lg font-semibold ${fromColor}`}
            >
              {fromName}
            </span>{" "}
            owes {toName}{" "}
            <span className="tabular-nums">
              {formatCurrency(settlement.amount)}
            </span>
          </>
        )}
      </p>
    </div>
  );
}

function SummaryStats({
  data,
  personNames,
}: {
  data: ReconciliationData;
  personNames: Map<string, string>;
}) {
  const stats = [
    { label: "Total shared", value: data.net_shared_spending },
    ...data.person_summaries.map((ps) => ({
      label: `${personNames.get(ps.person_id) ?? "Unknown"} paid`,
      value: ps.total_paid,
    })),
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="rounded-lg border border-border bg-card p-4 shadow-sm"
        >
          <p className="text-xs font-medium text-muted-foreground">
            {stat.label}
          </p>
          <p className="mt-1 text-lg font-semibold text-foreground tabular-nums text-right">
            {formatCurrency(stat.value)}
          </p>
        </div>
      ))}
    </div>
  );
}

function CategoryGroupRow({ group }: { group: CategoryGroupBreakdown }) {
  const [expanded, setExpanded] = useState(false);

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
}: {
  breakdowns: CategoryGroupBreakdown[];
  hasRefunds: boolean;
}) {
  if (breakdowns.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
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
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function buildCategoryGroupLookup(
  breakdowns: CategoryGroupBreakdown[],
): Map<string, string> {
  const lookup = new Map<string, string>();
  for (const group of breakdowns) {
    for (const cat of group.categories) {
      lookup.set(cat.category, group.group_name);
    }
  }
  return lookup;
}

function TransactionTable({
  transactions,
  personNames,
  personIndexMap,
  categoryGroups,
  isFinalized,
  onSplitUpdate,
  onTransactionUpdate,
  isSaving,
}: {
  transactions: ReconciliationTransaction[];
  personNames: Map<string, string>;
  personIndexMap: Map<string, number>;
  categoryGroups: Map<string, string>;
  isFinalized: boolean;
  onSplitUpdate: (
    splits: Array<{ transaction_id: string; payer_percentage: number }>,
  ) => void;
  onTransactionUpdate: (id: string, fields: TransactionUpdateFields) => void;
  isSaving: boolean;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [bulkMode, setBulkMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const personEntries = useMemo(
    () => [...personNames].map(([id, name]) => ({ id, name })),
    [personNames],
  );

  const sorted = useMemo(
    () =>
      [...transactions].sort(
        (a, b) =>
          b.date.localeCompare(a.date) || a.merchant.localeCompare(b.merchant),
      ),
    [transactions],
  );

  const colCount = 7 + personEntries.length + (bulkMode ? 1 : 0);

  const toggleSelected = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    setSelected((prev) =>
      prev.size === sorted.length
        ? new Set()
        : new Set(sorted.map((tx) => tx.id)),
    );
  }, [sorted]);

  const exitBulkMode = useCallback(() => {
    setBulkMode(false);
    setSelected(new Set());
  }, []);

  const handleBulkApply = useCallback(
    (percentage: number) => {
      onSplitUpdate(
        [...selected].map((id) => ({
          transaction_id: id,
          payer_percentage: percentage,
        })),
      );
      exitBulkMode();
    },
    [selected, onSplitUpdate, exitBulkMode],
  );

  const otherNameMap = useMemo(() => {
    const map = new Map<string, string>();
    const entries = [...personNames];
    for (const [id] of entries) {
      const other = entries.find(([otherId]) => otherId !== id);
      map.set(id, other?.[1] ?? "Other");
    }
    return map;
  }, [personNames]);

  if (transactions.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-medium text-lg text-foreground">Transactions</h2>
        {!isFinalized && !bulkMode && (
          <Button
            variant="secondary"
            size="sm"
            icon={<Pencil className="size-3.5" />}
            onClick={() => setBulkMode(true)}
          >
            Edit Splits
          </Button>
        )}
      </div>

      {bulkMode && (
        <div className="mb-4">
          <BulkSplitEditor
            selectedCount={selected.size}
            saving={isSaving}
            onApply={handleBulkApply}
            onCancel={exitBulkMode}
          />
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              {bulkMode && (
                <th className="pb-2 pr-2 w-8">
                  <input
                    type="checkbox"
                    checked={
                      selected.size === sorted.length && sorted.length > 0
                    }
                    onChange={toggleAll}
                    className="accent-primary"
                  />
                </th>
              )}
              <th className="pb-2 pr-4 font-medium">Date</th>
              <th className="pb-2 pr-4 font-medium">Merchant</th>
              <th className="pb-2 pr-4 font-medium">Category</th>
              <th className="pb-2 pr-4 font-medium">Group</th>
              <th className="pb-2 pr-4 font-medium">Paid by</th>
              <th className="pb-2 pr-4 text-right font-medium">Amount</th>
              <th className="pb-2 pr-4 text-right font-medium">Split</th>
              {personEntries.map((p) => (
                <th key={p.id} className="pb-2 text-right font-medium">
                  {p.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((tx) => {
              const payerPct = tx.payer_percentage ?? 50;
              const { payerShare, otherShare } = computeShares(
                Math.abs(tx.amount),
                payerPct,
              );
              const payerName =
                personNames.get(tx.payer_person_id) ?? "Unknown";
              const payerColor = getPersonAccentColor(
                personIndexMap.get(tx.payer_person_id) ?? -1,
              );
              const isExpanded = expandedId === tx.id;
              const canEdit = !isFinalized && !bulkMode;

              return (
                <TransactionRow
                  key={tx.id}
                  tx={tx}
                  payerShare={payerShare}
                  otherShare={otherShare}
                  payerName={payerName}
                  payerColor={payerColor}
                  otherName={otherNameMap.get(tx.payer_person_id) ?? "Other"}
                  categoryGroup={
                    categoryGroups.get(tx.category) ?? "Uncategorized"
                  }
                  personEntries={personEntries}
                  isExpanded={isExpanded}
                  canEdit={canEdit}
                  bulkMode={bulkMode}
                  isSelected={selected.has(tx.id)}
                  isSaving={isSaving}
                  colCount={colCount}
                  onToggleExpand={() =>
                    setExpandedId(isExpanded ? null : tx.id)
                  }
                  onToggleSelect={() => toggleSelected(tx.id)}
                  onTransactionUpdate={(fields) =>
                    onTransactionUpdate(tx.id, fields)
                  }
                  onCancel={() => setExpandedId(null)}
                />
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TransactionRow({
  tx,
  payerShare,
  otherShare,
  payerName,
  payerColor,
  otherName,
  categoryGroup,
  personEntries,
  isExpanded,
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
  tx: ReconciliationTransaction;
  payerShare: number;
  otherShare: number;
  payerName: string;
  payerColor: string;
  otherName: string;
  categoryGroup: string;
  personEntries: Array<{ id: string; name: string }>;
  isExpanded: boolean;
  canEdit: boolean;
  bulkMode: boolean;
  isSelected: boolean;
  isSaving: boolean;
  colCount: number;
  onToggleExpand: () => void;
  onToggleSelect: () => void;
  onTransactionUpdate: (fields: TransactionUpdateFields) => void;
  onCancel: () => void;
}) {
  return (
    <>
      <tr
        className={`border-b border-border-muted ${canEdit ? "cursor-pointer hover:bg-muted/50" : ""} ${isExpanded ? "bg-muted/30" : ""}`}
        onClick={canEdit ? onToggleExpand : undefined}
      >
        {bulkMode && (
          <td className="py-2 pr-2">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={onToggleSelect}
              onClick={(e) => e.stopPropagation()}
              className="accent-primary"
            />
          </td>
        )}
        <td className="py-2 pr-4 text-muted-foreground tabular-nums">
          {formatDate(tx.date)}
        </td>
        <td className="py-2 pr-4 text-foreground">{tx.merchant}</td>
        <td className="py-2 pr-4 text-muted-foreground">{tx.category}</td>
        <td className="py-2 pr-4 text-muted-foreground">{categoryGroup}</td>
        <td className="py-2 pr-4">
          <span
            className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${payerColor}`}
          >
            {payerName}
          </span>
        </td>
        <td
          className={`py-2 pr-4 text-right tabular-nums ${tx.amount < 0 ? "text-negative" : "text-positive"}`}
        >
          {formatCurrency(tx.amount)}
        </td>
        <td className="py-2 pr-4 text-right text-muted-foreground tabular-nums">
          {formatSplit(tx.payer_percentage)}
        </td>
        {personEntries.map((p) => (
          <td
            key={p.id}
            className="py-2 text-right text-muted-foreground tabular-nums"
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
            <TransactionEditor
              tx={tx}
              payerName={payerName}
              otherName={otherName}
              saving={isSaving}
              onSave={onTransactionUpdate}
              onCancel={onCancel}
            />
          </td>
        </tr>
      )}
    </>
  );
}

export function TransactionsPage() {
  const { year, month } = useMonthYear();
  const queryClient = useQueryClient();

  const { data: persons } = useQuery({
    queryKey: PERSONS_QUERY_KEY,
    queryFn: fetchPersons,
  });

  const reconciliationQueryKey = useMemo(
    () => ["reconciliation", year, month],
    [year, month],
  );
  const { data, isLoading, error } = useQuery({
    queryKey: reconciliationQueryKey,
    queryFn: () => fetchReconciliation(year, month),
  });

  const invalidateReconciliation = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: reconciliationQueryKey });
    queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
  }, [queryClient, reconciliationQueryKey]);

  const finalizeMutation = useMutation({
    mutationFn: () => finalizePeriod(year, month),
    onSuccess: invalidateReconciliation,
  });

  const unfinalizeMutation = useMutation({
    mutationFn: () => unfinalizePeriod(year, month),
    onSuccess: invalidateReconciliation,
  });

  const splitMutation = useMutation({
    mutationFn: (
      splits: Array<{ transaction_id: string; payer_percentage: number }>,
    ) => updateTransactionSplits(splits),
    onSuccess: invalidateReconciliation,
  });

  const editMutation = useMutation({
    mutationFn: ({
      id,
      fields,
    }: {
      id: string;
      fields: TransactionUpdateFields;
    }) => updateTransaction(id, fields),
    onSuccess: invalidateReconciliation,
  });

  const personNames = useMemo(
    () => new Map((persons ?? []).map((p) => [p.id, p.name])),
    [persons],
  );
  const personIndexMap = useMemo(() => {
    const map = new Map<string, number>();
    let i = 0;
    for (const id of personNames.keys()) {
      map.set(id, i++);
    }
    return map;
  }, [personNames]);
  const categoryGroupLookup = useMemo(
    () =>
      data
        ? buildCategoryGroupLookup(data.category_group_breakdowns)
        : new Map<string, string>(),
    [data],
  );

  const monthName = MONTHS[month - 1] ?? "";

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="flex items-center gap-2.5 font-semibold text-2xl text-foreground">
          <ArrowLeftRight className="size-6" />
          Transactions
        </h1>
        <MonthSelector />
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-destructive-border bg-destructive-muted p-4 text-sm text-destructive-muted-foreground"
        >
          {error.message}
        </div>
      )}

      {data && (
        <div className="space-y-6">
          <FinalizationBanner
            isFinalized={data.is_finalized}
            finalizedAt={data.finalized_at}
            onFinalize={() => finalizeMutation.mutate()}
            onUnfinalize={() => unfinalizeMutation.mutate()}
            isPending={
              finalizeMutation.isPending || unfinalizeMutation.isPending
            }
          />
          <UploadStatusBanner statuses={data.upload_statuses} />
          <SettlementCard
            data={data}
            personNames={personNames}
            personIndexMap={personIndexMap}
          />

          {data.transaction_count === 0 ? (
            <div className="py-8 text-center">
              <p className="text-muted-foreground">
                No shared transactions for {monthName} {year}.
              </p>
              <Link
                to="/upload"
                className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
              >
                <Upload className="size-4" />
                Upload a CSV to get started
              </Link>
            </div>
          ) : (
            <>
              <SummaryStats data={data} personNames={personNames} />
              <CategoryGroupBreakdownTable
                breakdowns={data.category_group_breakdowns}
                hasRefunds={data.total_shared_refunds > 0}
              />
              <AdjustmentExportSection
                persons={persons ?? []}
                year={year}
                month={month}
              />
              <TransactionTable
                transactions={data.transactions}
                personNames={personNames}
                personIndexMap={personIndexMap}
                categoryGroups={categoryGroupLookup}
                isFinalized={data.is_finalized}
                onSplitUpdate={(splits) => splitMutation.mutate(splits)}
                onTransactionUpdate={(id, fields) =>
                  editMutation.mutate({ id, fields })
                }
                isSaving={splitMutation.isPending || editMutation.isPending}
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
