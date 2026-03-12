import { apiFetch } from "@/lib/api";

export interface UploadStatus {
  person_id: string;
  person_name: string;
  has_uploaded: boolean;
  upload_count: number;
}

export interface Settlement {
  amount: number;
  from_person_id: string;
  to_person_id: string;
}

export interface PersonSummary {
  person_id: string;
  total_paid: number;
  total_share: number;
}

export interface CategoryBreakdown {
  category: string;
  group_id: string | null;
  group_name: string;
  total_amount: number;
  transaction_count: number;
}

export interface CategoryGroupBreakdown {
  group_id: string | null;
  group_name: string;
  total_amount: number;
  transaction_count: number;
  categories: CategoryBreakdown[];
}

export interface ReconciliationTransaction {
  id: string;
  date: string;
  merchant: string;
  category: string;
  account: string;
  amount: number;
  payer_person_id: string;
  payer_percentage: number | null;
}

export interface ReconciliationData {
  year: number;
  month: number;
  total_shared_spending: number;
  total_shared_refunds: number;
  net_shared_spending: number;
  person_summaries: PersonSummary[];
  settlement: Settlement | null;
  category_group_breakdowns: CategoryGroupBreakdown[];
  transaction_count: number;
  transactions: ReconciliationTransaction[];
  upload_statuses: UploadStatus[];
  unmapped_categories: string[];
  is_finalized: boolean;
  finalized_at: string | null;
}

export interface PeriodStatus {
  is_finalized: boolean;
  finalized_at: string | null;
  notes: string;
}

export function fetchReconciliation(
  year: number,
  month: number,
): Promise<ReconciliationData> {
  return apiFetch(`/api/v1/reconciliation?year=${year}&month=${month}`);
}

export function finalizePeriod(
  year: number,
  month: number,
  notes = "",
): Promise<PeriodStatus> {
  return apiFetch("/api/v1/reconciliation/finalize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ year, month, notes }),
  });
}

export function unfinalizePeriod(
  year: number,
  month: number,
): Promise<PeriodStatus> {
  return apiFetch("/api/v1/reconciliation/unfinalize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ year, month }),
  });
}

export function fetchPeriodStatus(
  year: number,
  month: number,
): Promise<PeriodStatus> {
  return apiFetch(
    `/api/v1/reconciliation/period-status?year=${year}&month=${month}`,
  );
}
