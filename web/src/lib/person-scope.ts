import { useEnumParam } from "@/hooks/useEnumParam";

/** The two-way lens shared by Budget, Dashboard, and Insights (Budget
 * relabels the personal option "My Budget"). */
export type PersonScope = "household" | "personal";

export const PERSON_SCOPE_OPTIONS: Array<{
  value: PersonScope;
  label: string;
}> = [
  { value: "household", label: "Household" },
  { value: "personal", label: "My Spending" },
];

const PERSON_SCOPES = new Set(PERSON_SCOPE_OPTIONS.map((o) => o.value));

/** URL `scope` param — same name, values, and default on every scoped page. */
export function usePersonScopeParam() {
  return useEnumParam("scope", PERSON_SCOPES, "household");
}
