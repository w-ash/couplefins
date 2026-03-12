import { ApiError } from "@/api/client";
import { apiFetch } from "@/lib/api";

export interface AdjustmentPreview {
  dedup_id: string;
  date: string;
  merchant: string;
  category: string;
  amount: number;
}

export interface AdjustmentPreviewData {
  adjustments: AdjustmentPreview[];
  person_name: string;
  adjustment_count: number;
}

export function fetchAdjustmentPreview(
  personId: string,
  year: number,
  month: number,
): Promise<AdjustmentPreviewData> {
  return apiFetch(`/api/v1/persons/${personId}/adjustments/${year}/${month}`);
}

export async function downloadAdjustmentCsv(
  personId: string,
  year: number,
  month: number,
): Promise<{ filename: string; rowCount: number }> {
  const response = await fetch(
    `/api/v1/persons/${personId}/export/${year}/${month}`,
  );

  if (!response.ok) {
    let code = "UNKNOWN_ERROR";
    let message = "Download failed";
    try {
      const body = await response.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch {
      // Non-JSON error response (e.g. gateway error)
    }
    throw new ApiError(response.status, code, message);
  }

  const text = await response.text();
  const rowCount = text.trim().split("\n").length - 1; // subtract header

  const disposition = response.headers.get("content-disposition");
  const filenameMatch = disposition?.match(/filename="(.+)"/);
  const filename = filenameMatch?.[1] ?? "adjustments.csv";

  const blob = new Blob([text], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 100);

  return { filename, rowCount };
}
