import { apiFetch } from "@/lib/api";

export interface SplitUpdate {
  transaction_id: string;
  payer_percentage: number;
}

export interface UpdateSplitsResult {
  updated_count: number;
}

export function updateTransactionSplits(
  splits: SplitUpdate[],
): Promise<UpdateSplitsResult> {
  return apiFetch("/api/v1/transactions/splits", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ splits }),
  });
}

export interface TransactionUpdateFields {
  date?: string;
  amount?: number;
  category?: string;
  tags?: string[];
  payer_percentage?: number;
}

export interface TransactionEdit {
  id: string;
  transaction_id: string;
  field_name: string;
  old_value: string;
  new_value: string;
  edited_at: string;
}

export interface UpdateTransactionResult {
  id: string;
  edits: TransactionEdit[];
}

export interface TransactionEditHistory {
  edits: TransactionEdit[];
}

export function updateTransaction(
  id: string,
  fields: TransactionUpdateFields,
): Promise<UpdateTransactionResult> {
  return apiFetch(`/api/v1/transactions/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
}

export function fetchTransactionEdits(
  id: string,
): Promise<TransactionEditHistory> {
  return apiFetch(`/api/v1/transactions/${id}/edits`);
}

export interface BulkUpdatePayload {
  transaction_ids: string[];
  category?: string;
  payer_percentage?: number;
}

export interface BulkUpdateResult {
  updated_count: number;
}

export function bulkUpdateTransactions(
  payload: BulkUpdatePayload,
): Promise<BulkUpdateResult> {
  return apiFetch("/api/v1/transactions/bulk-update", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export interface BulkModifyTagsPayload {
  transaction_ids: string[];
  action: "add" | "remove";
  tags: string[];
}

export interface BulkModifyTagsResult {
  updated_count: number;
}

export function bulkModifyTags(
  payload: BulkModifyTagsPayload,
): Promise<BulkModifyTagsResult> {
  return apiFetch("/api/v1/transactions/bulk-tags", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
