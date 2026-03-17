import type { PersonResponse } from "@/api/generated/model";

export type Person = PersonResponse;

export const PERSON_ACCENT_COLORS = [
  "bg-primary-muted text-primary-muted-foreground",
  "bg-accent text-accent-foreground",
] as const;

export function getPersonAccentColor(index: number): string {
  return PERSON_ACCENT_COLORS[
    index >= 0 ? index % PERSON_ACCENT_COLORS.length : 0
  ];
}
