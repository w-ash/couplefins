import { useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  CopyPlus,
  Info,
  PieChart,
  Plus,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router";
import {
  getGetBudgetOverviewQueryKey,
  useCopyBudgets,
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
import { Card } from "@/components/Card";
import { Combobox, type ComboboxOption } from "@/components/Combobox";
import { Dialog } from "@/components/Dialog";
import { ExpandChevron } from "@/components/ExpandChevron";
import { MonthPicker } from "@/components/MonthPicker";
import { PageHeader } from "@/components/PageHeader";
import { PageEmpty, PageError, PageLoading } from "@/components/PageStates";
import { ProgressBar } from "@/components/ProgressBar";
import { SectionHeader } from "@/components/SectionHeader";
import { SegmentedControl } from "@/components/SegmentedControl";
import { StatsGrid } from "@/components/StatsGrid";
import {
  type BudgetScope,
  type SortMode,
  useBudgetFilters,
  type ViewMode,
} from "@/lib/budget-filters";
import { useGroupIconMap } from "@/lib/categories";
import { getCategoryGroupIcon } from "@/lib/category-icons";
import { stepMonth } from "@/lib/date-range";
import {
  currentMonth,
  currentYear,
  formatCurrency,
  MONTHS,
  useMonthYear,
} from "@/lib/format";
import { getHealthStyle } from "@/lib/health-styles";
import { baseInputClass } from "@/lib/input-styles";
import { PAGE_PADDING } from "@/lib/layout";
import { usePersonMaps } from "@/lib/persons";
import { getPersonBarColor } from "@/types/person";

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
  healthStyle: { color: string; label: string };
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
          {healthStyle.label}
        </span>
      )}
    </div>
  );
}

function SpentBudgetLabel({
  spent,
  budget,
  hasBudget,
  breakdown,
}: {
  spent: number;
  budget: number | null;
  hasBudget: boolean;
  breakdown?: { household: number; personal: number } | null;
}) {
  const breakdownEl = breakdown ? (
    <span className="block text-xs text-muted-foreground">
      (household: {formatCurrency(breakdown.household)} · personal:{" "}
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
      {breakdownEl}
    </span>
  );
}

function BudgetGroupRow({
  status,
  viewMode,
  breakdown,
  icon,
  year,
  month,
  sourceBudgetAmount,
  onUpdate,
  onDelete,
  budgetQueryKey,
  getPersonIndex,
}: {
  status: GroupBudgetStatusResponse;
  viewMode: ViewMode;
  breakdown: { household: number; personal: number } | null;
  icon: string | null;
  year: number;
  month: number;
  sourceBudgetAmount: number | null;
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
  const hasBudget = status.monthly_budget != null;
  const pct =
    hasBudget && budget != null && budget > 0
      ? Math.min(100, (spent / budget) * 100)
      : 0;

  const budgetDelta = (() => {
    if (viewMode !== "monthly" || !hasBudget || status.monthly_budget == null)
      return null;
    if (sourceBudgetAmount == null) return "New this month";
    const diff = status.monthly_budget - sourceBudgetAmount;
    if (diff === 0) return null;
    const arrow = diff > 0 ? "\u2191" : "\u2193";
    return `${arrow} ${formatCurrency(Math.abs(diff))} from last month`;
  })();

  const ytdGap =
    viewMode === "ytd" &&
    hasBudget &&
    status.budgeted_months < month &&
    status.budgeted_months > 0
      ? `${status.budgeted_months} of ${month} months budgeted`
      : null;

  const deltaHint =
    budgetDelta || ytdGap ? (
      <span className="text-xs text-muted-foreground">
        {budgetDelta || ytdGap}
      </span>
    ) : null;

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
            {deltaHint}
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
                hasBudget={hasBudget}
                breakdown={breakdown}
              />
            </div>
          </div>

          {/* Desktop layout */}
          <div className="hidden min-w-0 flex-1 space-y-1.5 sm:block">
            <GroupHeader {...headerProps} />
            {deltaHint}
            {hasBudget && budget != null && (
              <ProgressBar pct={pct} barColor={healthStyle.barColor} />
            )}
          </div>

          <div className="hidden shrink-0 items-center gap-4 text-right sm:flex">
            <SpentBudgetLabel
              spent={spent}
              budget={budget}
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
                      {sourceBudgetAmount != null && (
                        <span className="text-xs text-muted-foreground">
                          Last: {formatCurrency(sourceBudgetAmount)}
                        </span>
                      )}
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
        <Dialog
          open={confirmDelete}
          onClose={() => setConfirmDelete(false)}
          size="sm"
          aria-labelledby={`delete-budget-${status.group_id}-title`}
        >
          <h3
            id={`delete-budget-${status.group_id}-title`}
            className="font-medium text-foreground"
          >
            Remove {status.group_name} budget for {MONTHS[month - 1]} {year}?
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
        </Dialog>
      )}
    </>
  );
}

function AddBudgetForm({
  unbudgetedGroups,
  onSave,
}: {
  unbudgetedGroups: GroupBudgetStatusResponse[];
  onSave: (groupId: string, amount: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [groupId, setGroupId] = useState("");
  const [amount, setAmount] = useState("");

  const groupOptions: ComboboxOption[] = useMemo(
    () =>
      unbudgetedGroups.map((g) => ({
        value: g.group_id,
        label: g.group_name,
      })),
    [unbudgetedGroups],
  );

  const selectedGroup = unbudgetedGroups.find((g) => g.group_id === groupId);
  const hasPersonalCategories =
    selectedGroup?.categories.some((c) => c.include_personal) ?? false;

  if (unbudgetedGroups.length === 0) return null;

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
          const parsed = Number.parseFloat(amount);
          if (!groupId || !Number.isFinite(parsed) || parsed <= 0) return;
          onSave(groupId, parsed);
          setOpen(false);
          setGroupId("");
          setAmount("");
        }}
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1fr_12rem] sm:items-end">
          <div className="min-w-0">
            <label
              htmlFor="budget-group"
              className="mb-1.5 block text-sm font-medium text-foreground"
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
              className="mb-1.5 block text-sm font-medium text-foreground"
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
              className={`w-full tabular-nums ${baseInputClass}`}
              required
            />
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
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
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <span>
              Avg: {formatCurrency(selectedGroup.average_monthly_spending)}
              {hasPersonalCategories && " (incl. personal)"}
            </span>
            {hasPersonalCategories && (
              <button
                type="button"
                className="rounded-md p-0.5 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Personal spending is included in this budget's totals because one or more categories have 'Include personal' enabled"
                title="Personal spending is included in this budget's totals because one or more categories have 'Include personal' enabled"
              >
                <Info className="size-3.5" />
              </button>
            )}
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

  const copyMutation = useCopyBudgets({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries({ queryKey }),
    },
  });

  const sourceBudgetMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const b of data?.source_budgets ?? []) {
      map.set(b.group_id, b.monthly_amount);
    }
    return map;
  }, [data?.source_budgets]);

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
  ): { household: number; personal: number } | null =>
    scope === "personal" &&
    s.household_spending != null &&
    s.personal_spending != null
      ? { household: s.household_spending, personal: s.personal_spending }
      : null;

  return (
    <div className={`mx-auto max-w-5xl ${PAGE_PADDING}`}>
      <PageHeader icon={<PieChart className="size-6" />} title="Budget">
        <div className="flex items-center gap-3">
          {data &&
            data.next_month_has_budgets === false &&
            (year < currentYear() ||
              (year === currentYear() && month < currentMonth())) &&
            (() => {
              const [ny, nm] = stepMonth(year, month, 1);
              return (
                <Link
                  to={`/budget?year=${ny}&month=${nm}`}
                  className="text-sm text-primary hover:underline"
                >
                  Set up {MONTHS[nm - 1]}
                </Link>
              );
            })()}
          <MonthPicker />
        </div>
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
          {/* Add budget form */}
          <AddBudgetForm
            unbudgetedGroups={allGroupsForAdd}
            onSave={(groupId, amount) =>
              saveMutation.mutate({
                data: {
                  group_id: groupId,
                  monthly_amount: amount,
                  year,
                  month,
                  is_personal: scope === "personal",
                },
              })
            }
          />

          {data.group_statuses.length === 0 && data.budgets.length === 0 ? (
            <div className="space-y-6">
              {data.copyable_source ? (
                (() => {
                  const { year: srcYear, month: srcMonth } =
                    data.copyable_source;
                  return (
                    <Card className="flex flex-col items-center py-8 text-center">
                      <CopyPlus className="size-10 text-muted-foreground" />
                      <h2 className="mt-4 text-lg font-medium text-foreground">
                        Copy budgets from {MONTHS[srcMonth - 1]} {srcYear}
                      </h2>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Start with your previous amounts and adjust from there
                      </p>
                      <div className="mt-4">
                        <Button
                          onClick={() =>
                            copyMutation.mutate({
                              data: {
                                source_year: srcYear,
                                source_month: srcMonth,
                                target_year: year,
                                target_month: month,
                              },
                            })
                          }
                          loading={copyMutation.isPending}
                          loadingText="Copying..."
                          icon={<CopyPlus className="size-4" />}
                        >
                          Copy budgets
                        </Button>
                      </div>
                      {copyMutation.isError && (
                        <p className="mt-3 text-sm text-destructive">
                          {copyMutation.error instanceof Error
                            ? copyMutation.error.message
                            : "Failed to copy budgets"}
                        </p>
                      )}
                    </Card>
                  );
                })()
              ) : (
                <PageEmpty
                  icon={<PieChart />}
                  heading="Add your first budget"
                  description={
                    scope === "personal"
                      ? "Use the form above to start tracking your personal spending."
                      : "Use the form above to start tracking household spending."
                  }
                />
              )}

              {unbudgetedGroups.length > 0 && (
                <section>
                  <SectionHeader
                    title="Spending this month"
                    description="Context for setting your budget amounts"
                  />
                  <div className="space-y-3">
                    {unbudgetedGroups.map((status) => (
                      <BudgetGroupRow
                        key={status.group_id}
                        status={status}
                        viewMode={viewMode}
                        breakdown={toBreakdown(status)}
                        icon={groupIconMap.get(status.group_id) ?? null}
                        year={year}
                        month={month}
                        sourceBudgetAmount={
                          sourceBudgetMap.get(status.group_id) ?? null
                        }
                        onUpdate={handleUpdate}
                        onDelete={handleDelete}
                        budgetQueryKey={queryKey}
                        getPersonIndex={getPersonIndex}
                      />
                    ))}
                  </div>
                </section>
              )}
            </div>
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
                      year={year}
                      month={month}
                      sourceBudgetAmount={
                        sourceBudgetMap.get(status.group_id) ?? null
                      }
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
                  <SectionHeader
                    title="Spending without a budget"
                    description="Groups with spending but no monthly target set"
                  />
                  <div className="space-y-3">
                    {unbudgetedGroups.map((status) => (
                      <BudgetGroupRow
                        key={status.group_id}
                        status={status}
                        viewMode={viewMode}
                        breakdown={toBreakdown(status)}
                        icon={groupIconMap.get(status.group_id) ?? null}
                        year={year}
                        month={month}
                        sourceBudgetAmount={
                          sourceBudgetMap.get(status.group_id) ?? null
                        }
                        onUpdate={handleUpdate}
                        onDelete={handleDelete}
                        budgetQueryKey={queryKey}
                        getPersonIndex={getPersonIndex}
                      />
                    ))}
                  </div>
                </section>
              )}

              {data.spending_drift != null && (
                <p className="mt-6 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Info className="size-3.5 shrink-0" />
                  Totals may be slightly off — check category mappings
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
