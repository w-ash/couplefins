import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, PieChart, Plus } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import {
  getGetBudgetOverviewQueryKey,
  useDeleteBudget,
  useGetBudgetOverview,
  usePostBudget,
  usePutBudget,
} from "@/api/generated/budgets/budgets";
import { usePatchCategory } from "@/api/generated/category-groups/category-groups";
import type {
  BudgetOverviewResponse,
  GroupBudgetStatusResponse,
} from "@/api/generated/model";
import { useGetPersons } from "@/api/generated/persons/persons";
import { Button } from "@/components/Button";
import { Combobox, type ComboboxOption } from "@/components/Combobox";
import { ExpandChevron } from "@/components/ExpandChevron";
import { MonthPicker } from "@/components/MonthPicker";
import { PageHeader } from "@/components/PageHeader";
import { PageEmpty, PageError, PageLoading } from "@/components/PageStates";
import { ProgressBar } from "@/components/ProgressBar";
import { SegmentedControl } from "@/components/SegmentedControl";
import { StatsGrid } from "@/components/StatsGrid";
import { useDialogSync } from "@/hooks/useDialogSync";
import {
  type BudgetScope,
  type SortMode,
  useBudgetFilters,
  type ViewMode,
} from "@/lib/budget-filters";
import { useGroupIconMap } from "@/lib/categories";
import { getCategoryGroupIcon } from "@/lib/category-icons";
import { formatCurrency, useMonthYear } from "@/lib/format";

import { baseInputClass } from "@/lib/input-styles";
import { PAGE_PADDING } from "@/lib/layout";
import { usePersonMaps } from "@/lib/persons";
import { getPersonBarColor } from "@/types/person";

const HEALTH_STYLES: Record<
  string,
  { color: string; barColor: string; label: string; iconColor: string }
> = {
  on_track: {
    color: "text-positive",
    barColor: "bg-primary",
    label: "On track",
    iconColor: "text-positive",
  },
  near_limit: {
    color: "text-warning-muted-foreground",
    barColor: "bg-warning",
    label: "Near limit",
    iconColor: "text-warning",
  },
  over_budget: {
    color: "text-destructive-muted-foreground",
    barColor: "bg-destructive",
    label: "Over budget",
    iconColor: "text-destructive",
  },
};

const DEFAULT_HEALTH = {
  color: "text-muted-foreground",
  barColor: "bg-muted",
  label: "",
  iconColor: "",
};

function getHealthStyle(health: string | null) {
  return health ? (HEALTH_STYLES[health] ?? DEFAULT_HEALTH) : DEFAULT_HEALTH;
}

function HealthIcon({ health }: { health: string | null }) {
  const style = getHealthStyle(health);
  if (!style.iconColor) return null;
  const Icon = health === "on_track" ? CheckCircle2 : AlertCircle;
  return <Icon className={`size-4 ${style.iconColor}`} />;
}

function SummaryStats({
  data,
  viewMode,
}: {
  data: BudgetOverviewResponse;
  viewMode: ViewMode;
}) {
  const budget =
    viewMode === "monthly" ? data.total_monthly_budget : data.total_ytd_budget;
  const spent =
    viewMode === "monthly" ? data.total_monthly_spent : data.total_ytd_spent;
  const remaining = budget - spent;

  return (
    <StatsGrid
      stats={[
        { label: "Total budget", value: formatCurrency(budget) },
        { label: "Total spent", value: formatCurrency(spent) },
        {
          label: "Remaining",
          value: formatCurrency(remaining),
          valueClassName:
            remaining < 0
              ? "text-destructive-muted-foreground"
              : "text-foreground",
        },
      ]}
    />
  );
}

function GroupHeader({
  groupName,
  icon,
  health,
  healthStyle,
  hasBudget,
}: {
  groupName: string;
  icon: string | null;
  health: string | null;
  healthStyle: { color: string };
  hasBudget: boolean;
}) {
  const GroupIcon = getCategoryGroupIcon(icon);
  return (
    <div className="flex items-center gap-2">
      <GroupIcon className="size-4 shrink-0 text-muted-foreground" />
      <span className="text-sm font-medium text-foreground">{groupName}</span>
      {hasBudget && (
        <span
          className={`flex items-center gap-1 text-xs ${healthStyle.color}`}
        >
          <HealthIcon health={health} />
          {getHealthStyle(health).label}
        </span>
      )}
    </div>
  );
}

function SpentBudgetLabel({
  spent,
  budget,
  remaining,
  hasBudget,
  breakdown,
}: {
  spent: number;
  budget: number | null;
  remaining: number | null;
  hasBudget: boolean;
  breakdown?: { shared: number; personal: number } | null;
}) {
  const breakdownEl = breakdown ? (
    <span className="block text-xs text-muted-foreground">
      (shared: {formatCurrency(breakdown.shared)} · personal:{" "}
      {formatCurrency(breakdown.personal)})
    </span>
  ) : null;

  if (!hasBudget || budget == null) {
    return (
      <span className="text-sm tabular-nums text-foreground">
        {formatCurrency(spent)}
        {breakdownEl}
      </span>
    );
  }
  return (
    <span className="text-sm tabular-nums">
      <span className="text-foreground">{formatCurrency(spent)}</span>
      <span className="text-muted-foreground">
        {" / "}
        {formatCurrency(budget)}
      </span>
      {remaining != null && (
        <span
          className={`ml-2 font-medium ${remaining < 0 ? "text-destructive-muted-foreground" : "text-muted-foreground"}`}
        >
          {formatCurrency(remaining)}
        </span>
      )}
      {breakdownEl}
    </span>
  );
}

function BudgetGroupRow({
  status,
  viewMode,
  breakdown,
  icon,
  onUpdate,
  onDelete,
  budgetQueryKey,
  getPersonIndex,
}: {
  status: GroupBudgetStatusResponse;
  viewMode: ViewMode;
  breakdown: { shared: number; personal: number } | null;
  icon: string | null;
  onUpdate: (budgetId: string, amount: number) => void;
  onDelete: (budgetId: string) => void;
  budgetQueryKey: readonly unknown[];
  getPersonIndex: (id: string) => number;
}) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const dialogRef = useDialogSync(confirmDelete);

  const patchCategory = usePatchCategory({
    mutation: {
      onSuccess: () =>
        queryClient.invalidateQueries({ queryKey: budgetQueryKey }),
    },
  });

  const budget =
    viewMode === "monthly" ? status.monthly_budget : status.ytd_budget;
  const spent =
    viewMode === "monthly" ? status.monthly_spent : status.ytd_spent;
  const health =
    viewMode === "monthly" ? status.monthly_health : status.ytd_health;
  const healthStyle = getHealthStyle(health);
  const remaining = budget != null ? budget - spent : null;
  const hasBudget = status.monthly_budget != null;
  const pct =
    hasBudget && budget != null && budget > 0
      ? Math.min(100, (spent / budget) * 100)
      : 0;

  const headerProps = {
    groupName: status.group_name,
    icon,
    health,
    healthStyle,
    hasBudget,
  };

  function handleEditSubmit() {
    const amount = Number.parseFloat(editValue);
    if (amount > 0 && status.budget_id) {
      onUpdate(status.budget_id, amount);
      setEditing(false);
    }
  }

  return (
    <>
      <div className="rounded-xl border border-border bg-card shadow-sm">
        {/* Main row */}
        <button
          type="button"
          className="flex w-full cursor-pointer items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50"
          aria-expanded={expanded}
          aria-label={`${expanded ? "Collapse" : "Expand"} ${status.group_name}`}
          onClick={() => setExpanded(!expanded)}
        >
          <ExpandChevron expanded={expanded} />

          {/* Mobile layout */}
          <div className="min-w-0 flex-1 sm:hidden">
            <GroupHeader {...headerProps} />
            {hasBudget && budget != null && (
              <div className="mt-1.5">
                <ProgressBar
                  pct={pct}
                  barColor={healthStyle.barColor}
                  showLabel
                />
              </div>
            )}
            <div className="mt-1">
              <SpentBudgetLabel
                spent={spent}
                budget={budget}
                remaining={remaining}
                hasBudget={hasBudget}
                breakdown={breakdown}
              />
            </div>
          </div>

          {/* Desktop layout */}
          <div className="hidden min-w-0 flex-1 space-y-1.5 sm:block">
            <GroupHeader {...headerProps} />
            {hasBudget && budget != null && (
              <ProgressBar
                pct={pct}
                barColor={healthStyle.barColor}
                showLabel
              />
            )}
          </div>

          <div className="hidden shrink-0 items-center gap-4 text-right sm:flex">
            <SpentBudgetLabel
              spent={spent}
              budget={budget}
              remaining={remaining}
              hasBudget={hasBudget}
              breakdown={breakdown}
            />
          </div>
        </button>

        {/* Expanded content — CSS grid transition */}
        <div
          className="grid transition-[grid-template-rows] duration-200"
          style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
        >
          <div className="overflow-hidden">
            <div className="border-t border-border-muted px-4 py-4">
              {/* Per-category breakdown */}
              {status.categories.length > 0 && (
                <div className="mb-4 space-y-2">
                  {status.categories.map((cat) => {
                    const catPct =
                      spent !== 0
                        ? Math.round((cat.total_amount / spent) * 100)
                        : 0;
                    return (
                      <div key={cat.category}>
                        <div className="flex items-center justify-between text-sm text-muted-foreground">
                          <span className="flex items-center gap-2">
                            {cat.category}
                            <span className="text-xs tabular-nums">
                              {catPct}%
                            </span>
                          </span>
                          <span className="flex items-center gap-3">
                            <label className="flex min-h-11 sm:min-h-0 cursor-pointer items-center gap-1.5 py-2 sm:py-0 text-xs">
                              <input
                                type="checkbox"
                                checked={cat.include_personal}
                                disabled={patchCategory.isPending}
                                onChange={(e) =>
                                  patchCategory.mutate({
                                    categoryName: cat.category,
                                    data: {
                                      include_personal: e.target.checked,
                                    },
                                  })
                                }
                                className="size-3.5 rounded border-border accent-primary disabled:opacity-50"
                              />
                              Include personal
                            </label>
                            <span className="tabular-nums">
                              {formatCurrency(cat.total_amount)}
                            </span>
                          </span>
                        </div>
                        {cat.include_personal &&
                        cat.personal_amounts.length > 0 ? (
                          <div className="mt-0.5 flex h-1 overflow-hidden rounded-full bg-muted">
                            {cat.household_amount > 0 && (
                              <div
                                className="h-full bg-household"
                                style={{
                                  width: `${(cat.household_amount / cat.total_amount) * 100}%`,
                                }}
                              />
                            )}
                            {cat.personal_amounts.map((pa) => (
                              <div
                                key={pa.person_id}
                                className={`h-full ${getPersonBarColor(getPersonIndex(pa.person_id))}`}
                                style={{
                                  width: `${(pa.amount / cat.total_amount) * 100}%`,
                                }}
                              />
                            ))}
                          </div>
                        ) : (
                          <div className="mt-0.5 h-0.5 rounded-full bg-muted">
                            <div
                              className="h-0.5 rounded-full bg-household"
                              style={{ width: `${catPct}%` }}
                            />
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {/* Legend for stacked bars */}
                  {status.categories.some(
                    (c) => c.include_personal && c.personal_amounts.length > 0,
                  ) && (
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1.5">
                        <span className="inline-block size-2 rounded-full bg-household" />
                        Household
                      </span>
                      {status.categories
                        .flatMap((c) => c.personal_amounts)
                        .filter(
                          (pa, i, arr) =>
                            arr.findIndex(
                              (x) => x.person_id === pa.person_id,
                            ) === i,
                        )
                        .map((pa) => (
                          <span
                            key={pa.person_id}
                            className="flex items-center gap-1.5"
                          >
                            <span
                              className={`inline-block size-2 rounded-full ${getPersonBarColor(getPersonIndex(pa.person_id))}`}
                            />
                            {pa.person_name}
                          </span>
                        ))}
                    </div>
                  )}
                </div>
              )}

              {/* Actions */}
              {hasBudget && status.budget_id && (
                <div className="flex items-center gap-2 border-t border-border-muted pt-3">
                  {editing ? (
                    <form
                      className="flex items-center gap-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        handleEditSubmit();
                      }}
                    >
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        min="0.01"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className={`w-28 tabular-nums ${baseInputClass}`}
                        aria-label="New budget amount"
                      />
                      <Button type="submit" size="sm">
                        Save Budget
                      </Button>
                      <button
                        type="button"
                        onClick={() => setEditing(false)}
                        className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                      >
                        Cancel
                      </button>
                    </form>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditValue(status.monthly_budget?.toString() ?? "");
                        setEditing(true);
                      }}
                    >
                      Edit amount
                    </Button>
                  )}

                  <button
                    type="button"
                    onClick={() => setConfirmDelete(true)}
                    className="ml-auto text-sm text-muted-foreground transition-colors hover:text-destructive-muted-foreground"
                  >
                    Remove budget
                  </button>
                </div>
              )}

              {/* Unbudgeted hint */}
              {!hasBudget && status.average_monthly_spending > 0 && (
                <p className="text-xs text-muted-foreground">
                  Avg: {formatCurrency(status.average_monthly_spending)}/mo
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      {hasBudget && (
        <dialog
          ref={dialogRef}
          onClose={() => setConfirmDelete(false)}
          className="mx-4 w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-lg backdrop:bg-black/40"
        >
          <h3 className="font-medium text-foreground">
            Remove {status.group_name} budget?
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Monthly tracking for this group will stop.
          </p>
          <div className="mt-5 flex gap-3">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setConfirmDelete(false)}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={() => {
                if (status.budget_id) onDelete(status.budget_id);
                setConfirmDelete(false);
              }}
              className="flex-1"
            >
              Remove Budget
            </Button>
          </div>
        </dialog>
      )}
    </>
  );
}

function AddBudgetForm({
  unbudgetedGroups,
  onSave,
}: {
  unbudgetedGroups: GroupBudgetStatusResponse[];
  onSave: (groupId: string, amount: number, effectiveFrom: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [groupId, setGroupId] = useState("");
  const [amount, setAmount] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(
    new Date().toISOString().slice(0, 10),
  );

  const groupOptions: ComboboxOption[] = useMemo(
    () =>
      unbudgetedGroups.map((g) => ({
        value: g.group_id,
        label: g.group_name,
      })),
    [unbudgetedGroups],
  );

  // Find the selected group to show average hint
  const selectedGroup = unbudgetedGroups.find((g) => g.group_id === groupId);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 rounded-xl border border-dashed border-border px-4 py-3 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
      >
        <Plus className="size-4" />
        Add budget
      </button>
    );
  }

  return (
    <div className="step-enter">
      <form
        className="rounded-xl border border-border bg-card p-4 shadow-sm"
        onSubmit={(e) => {
          e.preventDefault();
          if (groupId && Number.parseFloat(amount) > 0) {
            onSave(groupId, Number.parseFloat(amount), effectiveFrom);
            setOpen(false);
            setGroupId("");
            setAmount("");
          }
        }}
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1 sm:max-w-48">
            <label
              htmlFor="budget-group"
              className="mb-1 block text-sm font-medium text-foreground"
            >
              Category group
            </label>
            <Combobox
              mode="single"
              options={groupOptions}
              value={groupId}
              onChange={(v) => setGroupId(v as string)}
              placeholder="Select group..."
              allowCreate={false}
            />
          </div>
          <div>
            <label
              htmlFor="budget-amount"
              className="mb-1 block text-sm font-medium text-foreground"
            >
              Monthly amount
            </label>
            <input
              id="budget-amount"
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder={
                selectedGroup?.average_monthly_spending
                  ? `Avg: ${formatCurrency(selectedGroup.average_monthly_spending)}`
                  : "0.00"
              }
              className={`w-32 tabular-nums ${baseInputClass}`}
              required
            />
          </div>
          <div>
            <label
              htmlFor="budget-effective"
              className="mb-1 block text-sm font-medium text-foreground"
            >
              Effective from
            </label>
            <input
              id="budget-effective"
              type="date"
              value={effectiveFrom}
              onChange={(e) => setEffectiveFrom(e.target.value)}
              className={baseInputClass}
              required
            />
          </div>
          <Button type="submit" size="sm">
            Save Budget
          </Button>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Cancel
          </button>
        </div>
        {selectedGroup && selectedGroup.average_monthly_spending > 0 && (
          <p className="mt-2 text-xs text-muted-foreground">
            Average monthly spending:{" "}
            {formatCurrency(selectedGroup.average_monthly_spending)}
          </p>
        )}
      </form>
    </div>
  );
}

function sortStatuses(
  statuses: GroupBudgetStatusResponse[],
  mode: SortMode,
  viewMode: ViewMode,
): GroupBudgetStatusResponse[] {
  const sorted = [...statuses];
  switch (mode) {
    case "urgency": {
      const healthOrder = { over_budget: 0, near_limit: 1, on_track: 2 };
      sorted.sort((a, b) => {
        const ha = viewMode === "monthly" ? a.monthly_health : a.ytd_health;
        const hb = viewMode === "monthly" ? b.monthly_health : b.ytd_health;
        const oa = ha ? healthOrder[ha] : 3;
        const ob = hb ? healthOrder[hb] : 3;
        if (oa !== ob) return oa - ob;
        const sa = viewMode === "monthly" ? a.monthly_spent : a.ytd_spent;
        const sb = viewMode === "monthly" ? b.monthly_spent : b.ytd_spent;
        return sb - sa;
      });
      break;
    }
    case "spending": {
      sorted.sort((a, b) => {
        const sa = viewMode === "monthly" ? a.monthly_spent : a.ytd_spent;
        const sb = viewMode === "monthly" ? b.monthly_spent : b.ytd_spent;
        return sb - sa;
      });
      break;
    }
    case "name":
      sorted.sort((a, b) => a.group_name.localeCompare(b.group_name));
      break;
  }
  return sorted;
}

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
  { value: "urgency", label: "Urgency" },
  { value: "spending", label: "Spending" },
  { value: "name", label: "Name" },
];

export function BudgetPage() {
  const { year, month } = useMonthYear();
  const queryClient = useQueryClient();

  const { scope, setScope, viewMode, setViewMode, sortMode, setSortMode } =
    useBudgetFilters();

  const budgetOverviewParams = useMemo(
    () => ({ year, month, scope }),
    [year, month, scope],
  );
  const queryKey = getGetBudgetOverviewQueryKey(budgetOverviewParams);

  const {
    data: budgetResponse,
    isLoading,
    error,
    refetch,
  } = useGetBudgetOverview(budgetOverviewParams);
  const data = budgetResponse?.status === 200 ? budgetResponse.data : undefined;

  const groupIconMap = useGroupIconMap();
  const { data: personsResponse } = useGetPersons();
  const persons =
    personsResponse?.status === 200 ? personsResponse.data : undefined;
  const { getPersonIndex } = usePersonMaps(persons);

  const saveMutation = usePostBudget({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries({ queryKey }),
    },
  });

  const updateMutation = usePutBudget({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries({ queryKey }),
    },
  });

  const deleteMutation = useDeleteBudget({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries({ queryKey }),
    },
  });

  const handleUpdate = useCallback(
    (budgetId: string, amount: number) =>
      updateMutation.mutate({ budgetId, data: { monthly_amount: amount } }),
    [updateMutation.mutate],
  );

  const handleDelete = useCallback(
    (budgetId: string) => deleteMutation.mutate({ budgetId }),
    [deleteMutation.mutate],
  );

  const { budgetedGroups, unbudgetedGroups, allGroupsForAdd } = useMemo(() => {
    if (!data)
      return { budgetedGroups: [], unbudgetedGroups: [], allGroupsForAdd: [] };

    const budgeted = data.group_statuses.filter(
      (s) => s.monthly_budget != null,
    );
    const unbudgeted = data.group_statuses.filter(
      (s) => s.monthly_budget == null,
    );

    // For the add form: groups that don't have any budget at all
    const budgetedGroupIds = new Set(data.budgets.map((b) => b.group_id));
    const groupsForAdd = data.group_statuses.filter(
      (s) => !budgetedGroupIds.has(s.group_id),
    );

    return {
      budgetedGroups: sortStatuses(budgeted, sortMode, viewMode),
      unbudgetedGroups: sortStatuses(unbudgeted, sortMode, viewMode),
      allGroupsForAdd: groupsForAdd,
    };
  }, [data, sortMode, viewMode]);

  const toBreakdown = (
    s: GroupBudgetStatusResponse,
  ): { shared: number; personal: number } | null =>
    scope === "personal" &&
    s.shared_spending != null &&
    s.personal_spending != null
      ? { shared: s.shared_spending, personal: s.personal_spending }
      : null;

  return (
    <div className={`mx-auto max-w-5xl ${PAGE_PADDING}`}>
      <PageHeader icon={<PieChart className="size-6" />} title="Budget">
        <MonthPicker />
      </PageHeader>

      {/* Controls */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <SegmentedControl<BudgetScope>
          options={[
            { value: "household", label: "Household" },
            { value: "personal", label: "My Budget" },
          ]}
          value={scope}
          onChange={setScope}
          size="sm"
        />
        <SegmentedControl
          options={[
            { value: "monthly", label: "Monthly" },
            { value: "ytd", label: "Year to date" },
          ]}
          value={viewMode}
          onChange={setViewMode}
          size="sm"
        />
        <SegmentedControl
          options={SORT_OPTIONS}
          value={sortMode}
          onChange={setSortMode}
          size="sm"
        />
      </div>

      {isLoading && <PageLoading label="Loading budgets..." />}

      {error && <PageError error={error} onRetry={() => refetch()} />}

      {data && (
        <div className="space-y-6">
          {data.group_statuses.length === 0 && data.budgets.length === 0 ? (
            <PageEmpty
              icon={<PieChart />}
              heading="No budgets yet"
              description={
                scope === "personal"
                  ? "Add a budget above to start tracking your personal spending."
                  : "Add a budget above to start tracking shared spending."
              }
            />
          ) : (
            <>
              <SummaryStats data={data} viewMode={viewMode} />

              {/* Budgeted groups */}
              {budgetedGroups.length > 0 && (
                <div className="space-y-3">
                  {budgetedGroups.map((status) => (
                    <BudgetGroupRow
                      key={status.group_id}
                      status={status}
                      viewMode={viewMode}
                      breakdown={toBreakdown(status)}
                      icon={groupIconMap.get(status.group_id) ?? null}
                      onUpdate={handleUpdate}
                      onDelete={handleDelete}
                      budgetQueryKey={queryKey}
                      getPersonIndex={getPersonIndex}
                    />
                  ))}
                </div>
              )}

              {/* Unbudgeted groups with spending */}
              {unbudgetedGroups.length > 0 && (
                <section>
                  <h2 className="mb-1 font-medium text-lg text-foreground">
                    Spending without a budget
                  </h2>
                  <p className="mb-4 text-xs text-muted-foreground">
                    Groups with spending but no monthly target set
                  </p>
                  <div className="space-y-3">
                    {unbudgetedGroups.map((status) => (
                      <BudgetGroupRow
                        key={status.group_id}
                        status={status}
                        viewMode={viewMode}
                        breakdown={toBreakdown(status)}
                        icon={groupIconMap.get(status.group_id) ?? null}
                        onUpdate={handleUpdate}
                        onDelete={handleDelete}
                        budgetQueryKey={queryKey}
                        getPersonIndex={getPersonIndex}
                      />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}

          {/* Add budget form */}
          <AddBudgetForm
            unbudgetedGroups={allGroupsForAdd}
            onSave={(groupId, amount, effectiveFrom) =>
              saveMutation.mutate({
                data: {
                  group_id: groupId,
                  monthly_amount: amount,
                  effective_from: effectiveFrom,
                  is_personal: scope === "personal",
                },
              })
            }
          />
        </div>
      )}
    </div>
  );
}
