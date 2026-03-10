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

export async function fetchPersons(): Promise<Person[]> {
  const res = await fetch("/api/v1/persons/");
  if (!res.ok) throw new Error("Failed to fetch persons");
  return res.json();
}
