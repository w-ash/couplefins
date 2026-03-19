import type { PersonResponse } from "@/api/generated/model";

export type Person = PersonResponse;

export const PERSON_ACCENT_COLORS = [
  "bg-person-0-muted text-person-0-muted-foreground",
  "bg-person-1-muted text-person-1-muted-foreground",
] as const;

export const PERSON_BAR_COLORS = ["bg-person-0", "bg-person-1"] as const;

export function getPersonAccentColor(index: number): string {
  return PERSON_ACCENT_COLORS[
    index >= 0 ? index % PERSON_ACCENT_COLORS.length : 0
  ];
}

export function getPersonBarColor(index: number): string {
  return PERSON_BAR_COLORS[index >= 0 ? index % PERSON_BAR_COLORS.length : 0];
}
