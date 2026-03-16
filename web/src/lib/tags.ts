import { apiFetch } from "@/lib/api";

export const TAGS_QUERY_KEY = ["tags"] as const;

export function fetchTags(): Promise<string[]> {
  return apiFetch("/api/v1/tags");
}
