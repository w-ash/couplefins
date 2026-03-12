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

export function getPersonAccentColor(index: number): string {
  return PERSON_ACCENT_COLORS[
    index >= 0 ? index % PERSON_ACCENT_COLORS.length : 0
  ];
}

export const PERSONS_QUERY_KEY = ["persons"] as const;

export function fetchPersons(): Promise<Person[]> {
  return apiFetch("/api/v1/persons/");
}

export function updatePerson(
  personId: string,
  data: { adjustment_account: string },
): Promise<Person> {
  return apiFetch(`/api/v1/persons/${personId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}
