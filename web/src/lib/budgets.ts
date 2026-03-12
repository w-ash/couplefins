import { apiFetch } from "@/lib/api";

export interface CategorySpend {
  category: string;
  total_amount: number;
  transaction_count: number;
}

export interface GroupBudgetStatus {
  group_id: string;
  group_name: string;
  budget_id: string | null;
  monthly_budget: number | null;
  monthly_spent: number;
  ytd_budget: number | null;
  ytd_spent: number;
  monthly_health: "on_track" | "near_limit" | "over_budget" | null;
  ytd_health: "on_track" | "near_limit" | "over_budget" | null;
  average_monthly_spending: number;
  categories: CategorySpend[];
}

export interface BudgetItem {
  id: string;
  group_id: string;
  monthly_amount: number;
  effective_from: string;
}

export interface BudgetOverviewData {
  year: number;
  month: number;
  group_statuses: GroupBudgetStatus[];
  total_monthly_budget: number;
  total_monthly_spent: number;
  total_ytd_budget: number;
  total_ytd_spent: number;
  budgets: BudgetItem[];
}

export function fetchBudgetOverview(
  year: number,
  month: number,
): Promise<BudgetOverviewData> {
  return apiFetch(`/api/v1/budgets/overview?year=${year}&month=${month}`);
}

export function saveBudget(body: {
  group_id: string;
  monthly_amount: number;
  effective_from: string;
}): Promise<BudgetItem> {
  return apiFetch("/api/v1/budgets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function updateBudget(
  budgetId: string,
  body: { monthly_amount: number },
): Promise<BudgetItem> {
  return apiFetch(`/api/v1/budgets/${budgetId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteBudget(budgetId: string): Promise<void> {
  return apiFetch(`/api/v1/budgets/${budgetId}`, {
    method: "DELETE",
  });
}
