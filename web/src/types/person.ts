import type { PersonResponse } from "@/api/generated/model";

export type Person = PersonResponse;

export const PERSON_ACCENT_COLORS = [
  "bg-person-0-muted text-person-0-muted-foreground",
  "bg-person-1-muted text-person-1-muted-foreground",
] as const;

export const PERSON_BAR_COLORS = ["bg-person-0", "bg-person-1"] as const;

/** The palette slot for a person index; an unknown index (-1) gets slot 0. */
function personSlot(index: number): number {
  return index >= 0 ? index % PERSON_BAR_COLORS.length : 0;
}

export function getPersonAccentColor(index: number): string {
  return PERSON_ACCENT_COLORS[personSlot(index)];
}

export function getPersonBarColor(index: number): string {
  return PERSON_BAR_COLORS[personSlot(index)];
}

/** The CSS color for a person's chart marks (lines, swatches). */
export function getPersonChartColor(index: number): string {
  return `var(--person-${personSlot(index)})`;
}
