import { apiFetch } from "@/lib/api";
import type {
  PersonSummary,
  Settlement,
  UploadStatus,
} from "@/lib/reconciliation";

export interface MonthHistoryEntry {
  year: number;
  month: number;
  total_shared_spending: number;
  settlement_amount: number;
  settlement_from_person_id: string | null;
  settlement_to_person_id: string | null;
  is_finalized: boolean;
  is_settled: boolean;
  settled_at: string | null;
}

export interface DashboardPerson {
  id: string;
  name: string;
}

export interface DashboardData {
  current_month_year: number;
  current_month_month: number;
  current_month_total_shared_spending: number;
  current_month_net_shared_spending: number;
  current_month_transaction_count: number;
  current_month_person_summaries: PersonSummary[];
  current_month_settlement: Settlement | null;
  upload_statuses: UploadStatus[];
  ytd_total_shared_spending: number;
  ytd_settlement: Settlement | null;
  ytd_total_settled: number;
  month_history: MonthHistoryEntry[];
  persons: DashboardPerson[];
  unmapped_categories: string[];
  is_finalized: boolean;
  finalized_at: string | null;
}

export const DASHBOARD_QUERY_KEY = ["dashboard"] as const;

export function fetchDashboard(
  year?: number,
  month?: number,
): Promise<DashboardData> {
  const params = new URLSearchParams();
  if (year !== undefined) params.set("year", String(year));
  if (month !== undefined) params.set("month", String(month));
  const qs = params.toString();
  return apiFetch(`/api/v1/dashboard${qs ? `?${qs}` : ""}`);
}
