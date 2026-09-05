import { useEnumParam } from "@/hooks/useEnumParam";
import { monthStartEnd } from "@/lib/date-range";
import { usePersonScopeParam } from "@/lib/person-scope";
import type { TransactionsRange } from "@/lib/transaction-links";

export type InsightsPeriod = "month" | "ytd";
export type InsightsChart = "flow" | "donut" | "bars";
export type InsightsGroupBy = "group" | "category" | "merchant";

export const INSIGHTS_PERIOD_OPTIONS: Array<{
  value: InsightsPeriod;
  label: string;
}> = [
  { value: "month", label: "Month" },
  { value: "ytd", label: "Year to date" },
];

export const INSIGHTS_CHART_OPTIONS: Array<{
  value: InsightsChart;
  label: string;
}> = [
  { value: "flow", label: "Flow" },
  { value: "donut", label: "Donut" },
  { value: "bars", label: "Bars" },
];

export const INSIGHTS_GROUP_BY_OPTIONS: Array<{
  value: InsightsGroupBy;
  label: string;
}> = [
  { value: "group", label: "Groups" },
  { value: "category", label: "Categories" },
  { value: "merchant", label: "Merchants" },
];

const PERIODS = new Set(INSIGHTS_PERIOD_OPTIONS.map((o) => o.value));
const CHARTS = new Set(INSIGHTS_CHART_OPTIONS.map((o) => o.value));
const GROUP_BYS = new Set(INSIGHTS_GROUP_BY_OPTIONS.map((o) => o.value));

/**
 * Insights view state, all in the URL so a view is shareable and Back
 * restores it. `period` (not Budget's `view`) because the chart type is a
 * separate axis here.
 */
export function useInsightsFilters() {
  const [scope, setScope] = usePersonScopeParam();
  const [period, setPeriod] = useEnumParam("period", PERIODS, "month");
  const [chart, setChart] = useEnumParam("chart", CHARTS, "flow");
  const [groupBy, setGroupBy] = useEnumParam("by", GROUP_BYS, "group");
  return {
    scope,
    setScope,
    period,
    setPeriod,
    chart,
    setChart,
    groupBy,
    setGroupBy,
  };
}

/** The Transactions date range a period maps to: the month, or Jan 1 through
 * the selected month's last day. */
export function periodRange(
  year: number,
  month: number,
  period: InsightsPeriod,
): TransactionsRange {
  if (period === "month") return { year, month };
  return {
    startDate: `${year}-01-01`,
    endDate: monthStartEnd(year, month).endDate,
  };
}
