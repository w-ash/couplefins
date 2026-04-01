import { useEnumParam } from "@/hooks/useEnumParam";

export type DashboardScope = "household" | "personal" | "all";

const DASHBOARD_SCOPES = new Set<DashboardScope>([
  "household",
  "personal",
  "all",
]);

export function useDashboardFilters() {
  const [scope, setScope] = useEnumParam(
    "scope",
    DASHBOARD_SCOPES,
    "household",
  );
  return { scope, setScope };
}
