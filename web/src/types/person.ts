import { apiFetch } from "@/lib/api";

export interface Person {
  id: string;
  name: string;
  adjustment_account: string;
}

export const PERSON_ACCENT_COLORS = [
  "bg-primary-muted text-primary-muted-foreground",
  "bg-accent text-accent-foreground",
] as const;

export const PERSONS_QUERY_KEY = ["persons"] as const;

export function fetchPersons(): Promise<Person[]> {
  return apiFetch("/api/v1/persons/", undefined, "Failed to fetch persons");
}
