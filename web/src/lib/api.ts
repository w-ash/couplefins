import { customFetch } from "@/api/client";

/**
 * Thin wrapper over customFetch that unwraps the {data, status, headers}
 * envelope for manual (non-Orval) call sites.
 */
export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const result = await customFetch<{ data: T }>(url, init ?? {});
  return result.data;
}
