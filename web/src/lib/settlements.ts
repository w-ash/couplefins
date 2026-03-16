import { apiFetch } from "@/lib/api";
import type { DashboardPerson } from "@/lib/dashboard";
import type { UploadStatus } from "@/lib/reconciliation";

export interface Owed {
  amount: number;
  from_person_id: string;
  to_person_id: string;
}

export interface SettlementRecord {
  id: string;
  year: number;
  month: number;
  amount: number;
  from_person_id: string;
  to_person_id: string;
  method: string | null;
  is_waived: boolean;
  notes: string;
  settled_at: string;
  created_at: string;
  linked_transaction_ids: string[];
}

export interface SettleUpData {
  year: number;
  month: number;
  owed: Owed | null;
  recorded_settlements: SettlementRecord[];
  remaining_balance: number;
  upload_statuses: UploadStatus[];
  persons: DashboardPerson[];
  is_finalized: boolean;
  finalized_at: string | null;
}

export const SETTLE_UP_QUERY_KEY = ["settle-up"] as const;

export function fetchSettleUpData(
  year: number,
  month: number,
): Promise<SettleUpData> {
  return apiFetch(`/api/v1/settle-up?year=${year}&month=${month}`);
}

export function recordSettlement(body: {
  year: number;
  month: number;
  amount: number;
  from_person_id: string;
  to_person_id: string;
  method: string;
  notes?: string;
  settled_at?: string;
  linked_transaction_ids?: string[];
}): Promise<SettlementRecord> {
  return apiFetch("/api/v1/settlements", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function waiveSettlement(body: {
  year: number;
  month: number;
  from_person_id: string;
  to_person_id: string;
  notes?: string;
}): Promise<SettlementRecord> {
  return apiFetch("/api/v1/settlements/waive", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteSettlement(
  settlementId: string,
): Promise<{ deleted: boolean }> {
  return apiFetch(`/api/v1/settlements/${settlementId}`, {
    method: "DELETE",
  });
}
