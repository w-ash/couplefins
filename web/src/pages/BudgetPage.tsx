import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  PieChart,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/Button";
import { MonthSelector } from "@/components/MonthSelector";
import { PageEmpty, PageError, PageLoading } from "@/components/PageStates";
import type { BudgetOverviewData, GroupBudgetStatus } from "@/lib/budgets";
import {
  deleteBudget,
  fetchBudgetOverview,
  saveBudget,
  updateBudget,
} from "@/lib/budgets";
import {
  CATEGORY_GROUPS_QUERY_KEY,
  fetchCategoryGroups,
} from "@/lib/categories";
import { getCategoryGroupIcon } from "@/lib/category-icons";
import { formatCurrency, useMonthYear } from "@/lib/format";

type ViewMode = "monthly" | "ytd";
type SortMode = "urgency" | "spending" | "name";

function healthColor(health: string | null): string {
  switch (health) {
    case "over_budget":
      return "text-destructive-muted-foreground";
    case "near_limit":
      return "text-warning-muted-foreground";
    case "on_track":
      return "text-positive";
    default:
      return "text-muted-foreground";
  }
}

function healthBarColor(health: string | null): string {
  switch (health) {
    case "over_budget":
      return "bg-destructive";
    case "near_limit":
      return "bg-warning";
    case "on_track":
      return "bg-primary";
    default:
      return "bg-muted";
  }
}

function healthLabel(health: string | null): string {
  switch (health) {
    case "over_budget":
      return "Over budget";
    case "near_limit":
      return "Near limit";
    case "on_track":
      return "On track";
    default:
      return "";
  }
}

function HealthIcon({ health }: { health: string | null }) {
  if (health === "on_track")
    return <CheckCircle2 className="size-4 text-positive" />;
  if (health === "near_limit")
    return <AlertCircle className="size-4 text-warning" />;
  if (health === "over_budget")
    return <AlertCircle className="size-4 text-destructive" />;
  return null;
}

function SummaryStats({
  data,
  viewMode,
}: {
  data: BudgetOverviewData;
  viewMode: ViewMode;
}) {
  const budget =
    viewMode === "monthly" ? data.total_monthly_budget : data.total_ytd_budget;
  const spent =
    viewMode === "monthly" ? data.total_monthly_spent : data.total_ytd_spent;
  const remaining = budget - spent;

  return (
    <div className="grid grid-cols-3 gap-3">
      <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
        <p className="text-xs font-medium text-muted-foreground">
          Total budget
        </p>
        <p className="mt-1 text-right text-lg font-semibold text-foreground tabular-nums">
          {formatCurrency(budget)}
        </p>
      </div>
      <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
        <p className="text-xs font-medium text-muted-foreground">Total spent</p>
        <p className="mt-1 text-right text-lg font-semibold text-foreground tabular-nums">
          {formatCurrency(spent)}
        </p>
      </div>
      <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
        <p className="text-xs font-medium text-muted-foreground">Remaining</p>
        <p
          className={`mt-1 text-right text-lg font-semibold tabular-nums ${remaining < 0 ? "text-destructive-muted-foreground" : "text-foreground"}`}
        >
          {formatCurrency(remaining)}
        </p>
      </div>
    </div>
  );
}

function ProgressBar({
  spent,
  budget,
  health,
}: {
  spent: number;
  budget: number;
  health: string | null;
}) {
  const pct = budget > 0 ? Math.min(100, (spent / budget) * 100) : 0;
  return (
    <div className="h-2 w-full rounded-full bg-muted">
      <div
        className={`h-2 rounded-full transition-[width,background-color] duration-200 ${healthBarColor(health)}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function BudgetGroupRow({
  status,
  viewMode,
  icon,
  onUpdate,
  onDelete,
}: {
  status: GroupBudgetStatus;
  viewMode: ViewMode;
  icon: string | null;
  onUpdate: (budgetId: string, amount: number) => void;
  onDelete: (budgetId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const GroupIcon = getCategoryGroupIcon(icon);

  const budget =
    viewMode === "monthly" ? status.monthly_budget : status.ytd_budget;
  const spent =
    viewMode === "monthly" ? status.monthly_spent : status.ytd_spent;
  const health =
    viewMode === "monthly" ? status.monthly_health : status.ytd_health;
  const remaining = budget != null ? budget - spent : null;
  const hasBudget = status.monthly_budget != null;

  function handleEditSubmit() {
    const amount = Number.parseFloat(editValue);
    if (amount > 0 && status.budget_id) {
      onUpdate(status.budget_id, amount);
      setEditing(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card shadow-sm">
      {/* Main row */}
      <button
        type="button"
        className="flex w-full cursor-pointer items-center gap-3 px-4 py-3 text-left"
        aria-expanded={expanded}
        aria-label={`${expanded ? "Collapse" : "Expand"} ${status.group_name}`}
        onClick={() => setExpanded(!expanded)}
      >
        <span className="shrink-0">
          {expanded ? (
            <ChevronDown className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground" />
          )}
        </span>

        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-center gap-2">
            <GroupIcon className="size-4 shrink-0 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">
              {status.group_name}
            </span>
            {hasBudget && (
              <span
                className={`flex items-center gap-1 text-xs ${healthColor(health)}`}
              >
                <HealthIcon health={health} />
                {healthLabel(health)}
              </span>
            )}
          </div>
          {hasBudget && budget != null && (
            <ProgressBar spent={spent} budget={budget} health={health} />
          )}
        </div>

        <div className="flex shrink-0 items-center gap-4 text-right">
          {hasBudget && budget != null ? (
            <>
              <div className="text-sm tabular-nums">
                <span className="text-foreground">{formatCurrency(spent)}</span>
                <span className="text-muted-foreground">
                  {" / "}
                  {formatCurrency(budget)}
                </span>
              </div>
              <div
                className={`text-sm font-medium tabular-nums ${remaining != null && remaining < 0 ? "text-destructive-muted-foreground" : "text-muted-foreground"}`}
              >
                {remaining != null && formatCurrency(remaining)}
              </div>
            </>
          ) : (
            <span className="text-sm tabular-nums text-foreground">
              {formatCurrency(spent)}
            </span>
          )}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border-muted px-4 py-4">
          {/* Per-category breakdown */}
          {status.categories.length > 0 && (
            <div className="mb-4 space-y-1.5">
              {status.categories.map((cat) => (
                <div
                  key={cat.category}
                  className="flex justify-between text-sm text-muted-foreground"
                >
                  <span>{cat.category}</span>
                  <span className="tabular-nums">
                    {formatCurrency(cat.total_amount)}
                  </span>
                </div>
              ))}
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
                    step="0.01"
                    min="0.01"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="w-28 rounded border border-input bg-background px-2 py-1 text-sm tabular-nums"
                    aria-label="New budget amount"
                  />
                  <button
                    type="submit"
                    className="rounded bg-primary px-2 py-1 text-xs font-medium text-primary-foreground"
                  >
                    Save Budget
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditing(false)}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X className="size-4" />
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

              {confirmDelete ? (
                <span className="ml-auto flex items-center gap-2 text-xs">
                  <span className="text-destructive-muted-foreground">
                    Delete?
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      if (status.budget_id) onDelete(status.budget_id);
                      setConfirmDelete(false);
                    }}
                    className="font-medium text-destructive-muted-foreground hover:text-destructive"
                  >
                    Yes
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    className="text-muted-foreground"
                  >
                    No
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setConfirmDelete(true);
                  }}
                  className="ml-auto text-muted-foreground hover:text-destructive-muted-foreground"
                  aria-label={`Delete ${status.group_name} budget`}
                >
                  <Trash2 className="size-4" />
                </button>
              )}
            </div>
          )}

          {/* Unbudgeted hint */}
          {!hasBudget && status.average_monthly_spending > 0 && (
            <p className="text-xs text-muted-foreground">
              Avg: {formatCurrency(status.average_monthly_spending)}/mo
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function AddBudgetForm({
  unbudgetedGroups,
  onSave,
}: {
  unbudgetedGroups: GroupBudgetStatus[];
  onSave: (groupId: string, amount: number, effectiveFrom: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [groupId, setGroupId] = useState("");
  const [amount, setAmount] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(
    new Date().toISOString().slice(0, 10),
  );

  // Find the selected group to show average hint
  const selectedGroup = unbudgetedGroups.find((g) => g.group_id === groupId);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 rounded-lg border border-dashed border-border px-4 py-3 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
      >
        <Plus className="size-4" />
        Add budget
      </button>
    );
  }

  return (
    <form
      className="rounded-lg border border-border bg-card p-4 shadow-sm"
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
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label
            htmlFor="budget-group"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Category group
          </label>
          <select
            id="budget-group"
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-1.5 text-sm"
            required
          >
            <option value="">Select group...</option>
            {unbudgetedGroups.map((g) => (
              <option key={g.group_id} value={g.group_id}>
                {g.group_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label
            htmlFor="budget-amount"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Monthly amount
          </label>
          <input
            id="budget-amount"
            type="number"
            step="0.01"
            min="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder={
              selectedGroup?.average_monthly_spending
                ? `Avg: ${formatCurrency(selectedGroup.average_monthly_spending)}`
                : "0.00"
            }
            className="w-32 rounded border border-input bg-background px-2 py-1.5 text-sm tabular-nums"
            required
          />
        </div>
        <div>
          <label
            htmlFor="budget-effective"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Effective from
          </label>
          <input
            id="budget-effective"
            type="date"
            value={effectiveFrom}
            onChange={(e) => setEffectiveFrom(e.target.value)}
            className="rounded border border-input bg-background px-2 py-1.5 text-sm"
            required
          />
        </div>
        <button
          type="submit"
          className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground"
        >
          Save Budget
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>
      {selectedGroup && selectedGroup.average_monthly_spending > 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          Average monthly spending:{" "}
          {formatCurrency(selectedGroup.average_monthly_spending)}
        </p>
      )}
    </form>
  );
}

function sortStatuses(
  statuses: GroupBudgetStatus[],
  mode: SortMode,
  viewMode: ViewMode,
): GroupBudgetStatus[] {
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

export function BudgetPage() {
  const { year, month } = useMonthYear();
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<ViewMode>("monthly");
  const [sortMode, setSortMode] = useState<SortMode>("urgency");

  const queryKey = ["budget-overview", year, month];

  const { data, isLoading, error, refetch } = useQuery({
    queryKey,
    queryFn: () => fetchBudgetOverview(year, month),
  });

  const { data: categoryGroups } = useQuery({
    queryKey: [...CATEGORY_GROUPS_QUERY_KEY],
    queryFn: fetchCategoryGroups,
  });

  const groupIconMap = useMemo(
    () => new Map((categoryGroups ?? []).map((g) => [g.id, g.icon])),
    [categoryGroups],
  );

  const saveMutation = useMutation({
    mutationFn: (args: {
      group_id: string;
      monthly_amount: number;
      effective_from: string;
    }) => saveBudget(args),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const updateMutation = useMutation({
    mutationFn: (args: { budgetId: string; amount: number }) =>
      updateBudget(args.budgetId, { monthly_amount: args.amount }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  const deleteMutation = useMutation({
    mutationFn: (budgetId: string) => deleteBudget(budgetId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

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

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="flex items-center gap-2.5 font-semibold text-2xl text-foreground">
          <PieChart className="size-6" />
          Budget
        </h1>
        <MonthSelector />
      </div>

      {/* Controls */}
      <div className="mb-6 flex items-center gap-3">
        <div className="flex rounded-lg border border-input">
          <button
            type="button"
            onClick={() => setViewMode("monthly")}
            className={`px-3 py-1.5 text-sm ${viewMode === "monthly" ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:text-foreground"} rounded-l-lg`}
          >
            Monthly
          </button>
          <button
            type="button"
            onClick={() => setViewMode("ytd")}
            className={`px-3 py-1.5 text-sm ${viewMode === "ytd" ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:text-foreground"} rounded-r-lg`}
          >
            Year to date
          </button>
        </div>
        <select
          aria-label="Sort order"
          value={sortMode}
          onChange={(e) => setSortMode(e.target.value as SortMode)}
          className="rounded-lg border border-input bg-card px-3 py-1.5 text-sm text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none"
        >
          <option value="urgency">Sort: Urgency</option>
          <option value="spending">Sort: Spending</option>
          <option value="name">Sort: Name</option>
        </select>
      </div>

      {isLoading && <PageLoading label="Loading budgets..." />}

      {error && <PageError error={error} onRetry={() => refetch()} />}

      {data && (
        <div className="space-y-6">
          {data.group_statuses.length === 0 && data.budgets.length === 0 ? (
            <PageEmpty
              icon={<PieChart />}
              heading="No budgets yet"
              description="Add a budget above to start tracking shared spending."
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
                      icon={groupIconMap.get(status.group_id) ?? null}
                      onUpdate={(budgetId, amount) =>
                        updateMutation.mutate({ budgetId, amount })
                      }
                      onDelete={(budgetId) => deleteMutation.mutate(budgetId)}
                    />
                  ))}
                </div>
              )}

              {/* Unbudgeted groups with spending */}
              {unbudgetedGroups.length > 0 && (
                <div>
                  <h2 className="mb-4 font-medium text-lg text-foreground">
                    Spending without a budget
                  </h2>
                  <div className="space-y-3">
                    {unbudgetedGroups.map((status) => (
                      <BudgetGroupRow
                        key={status.group_id}
                        status={status}
                        viewMode={viewMode}
                        icon={groupIconMap.get(status.group_id) ?? null}
                        onUpdate={(budgetId, amount) =>
                          updateMutation.mutate({ budgetId, amount })
                        }
                        onDelete={(budgetId) => deleteMutation.mutate(budgetId)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Add budget form */}
          <AddBudgetForm
            unbudgetedGroups={allGroupsForAdd}
            onSave={(groupId, amount, effectiveFrom) =>
              saveMutation.mutate({
                group_id: groupId,
                monthly_amount: amount,
                effective_from: effectiveFrom,
              })
            }
          />
        </div>
      )}
    </div>
  );
}
