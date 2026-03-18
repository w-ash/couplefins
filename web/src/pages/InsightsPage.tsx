import { TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { useGetSpendingTrends } from "@/api/generated/insights/insights";
import type {
  BudgetLineItem,
  CategorySpendingItem,
  GroupSummaryItem,
  MonthlyGroupSpendingItem,
  MonthlyTotalItem,
  SpendingTrendsResponse,
} from "@/api/generated/model";
import { ComparisonCard } from "@/components/ComparisonCard";
import { MonthPicker } from "@/components/MonthPicker";
import { PageHeader } from "@/components/PageHeader";
import { PageEmpty, PageError, PageLoading } from "@/components/PageStates";
import { SegmentedControl } from "@/components/SegmentedControl";
import { SettlementTrendChart } from "@/components/SettlementTrendChart";
import { SparklineCard } from "@/components/SparklineCard";
import { StatsGrid } from "@/components/StatsGrid";
import { useGroupIconMap } from "@/lib/categories";
import { getChartColor } from "@/lib/chart-colors";
import {
  currentYear,
  formatCurrency,
  MONTHS,
  useMonthYear,
} from "@/lib/format";
import { selectInputClass } from "@/lib/input-styles";
import { usePersonMaps } from "@/lib/persons";

function YearSelector() {
  const [searchParams, setSearchParams] = useSearchParams();
  const year = Number(searchParams.get("year")) || currentYear();
  const thisYear = currentYear();
  const years = Array.from({ length: 5 }, (_, i) => thisYear - i);

  return (
    <select
      value={year}
      onChange={(e) => {
        const params = new URLSearchParams(searchParams);
        params.set("year", e.target.value);
        setSearchParams(params);
      }}
      className={selectInputClass}
      aria-label="Select year"
    >
      {years.map((y) => (
        <option key={y} value={y}>
          {y}
        </option>
      ))}
    </select>
  );
}

interface GroupChartData {
  groupId: string | null;
  groupName: string;
  data: { month: number; amount: number }[];
  ytdTotal: number;
}

function groupSpendingByGroupId(
  spending: MonthlyGroupSpendingItem[],
): Map<string | null, { month: number; amount: number }[]> {
  const byGroup = new Map<string | null, { month: number; amount: number }[]>();
  for (const item of spending) {
    const key = item.group_id;
    if (!byGroup.has(key)) byGroup.set(key, []);
    byGroup.get(key)?.push({ month: item.month, amount: item.amount });
  }
  return byGroup;
}

function buildGroupCharts(
  spending: MonthlyGroupSpendingItem[],
  summaries: GroupSummaryItem[],
): GroupChartData[] {
  const byGroup = groupSpendingByGroupId(spending);

  return summaries.map((gs) => ({
    groupId: gs.group_id,
    groupName: gs.group_name,
    data: (byGroup.get(gs.group_id) ?? []).sort((a, b) => a.month - b.month),
    ytdTotal: gs.ytd_total,
  }));
}

function buildCategoryMap(
  spending: MonthlyGroupSpendingItem[],
  month: number,
): Map<string | null, CategorySpendingItem[]> {
  const result = new Map<string | null, CategorySpendingItem[]>();
  for (const item of spending) {
    if (item.month === month) {
      result.set(item.group_id, item.categories);
    }
  }
  return result;
}

function buildBudgetMap(budgetLines: BudgetLineItem[]): Map<string, number> {
  return new Map(budgetLines.map((bl) => [bl.group_id, bl.monthly_budget]));
}

function buildStats(data: SpendingTrendsResponse) {
  const { monthly_totals: totals, group_summaries: groups } = data;
  if (totals.length === 0) return [];

  const ytdTotal = groups.reduce((sum, g) => sum + g.ytd_total, 0);
  const avg = ytdTotal / totals.length;
  const highest = totals.reduce<MonthlyTotalItem>(
    (max, t) => (t.total_amount > max.total_amount ? t : max),
    totals[0],
  );
  const largestGroup = groups[0];

  const stats = [
    { label: "YTD shared spending", value: formatCurrency(ytdTotal) },
    { label: "Monthly average", value: formatCurrency(avg) },
    {
      label: "Highest month",
      value: `${MONTHS[highest.month - 1].slice(0, 3)}: ${formatCurrency(highest.total_amount)}`,
    },
    {
      label: "Largest category",
      value: largestGroup?.group_name ?? "None",
    },
  ];

  if (totals.length >= 2) {
    const sorted = [...totals].sort((a, b) => a.month - b.month);
    const latest = sorted[sorted.length - 1];
    const previous = sorted[sorted.length - 2];
    const delta = latest.total_amount - previous.total_amount;
    const pct =
      previous.total_amount > 0
        ? ((delta / previous.total_amount) * 100).toFixed(0)
        : "0";
    const sign = delta >= 0 ? "+" : "";
    stats.push({
      label: `${MONTHS[latest.month - 1].slice(0, 3)} vs ${MONTHS[previous.month - 1].slice(0, 3)}`,
      value: `${sign}${pct}% (${formatCurrency(Math.abs(delta))})`,
    });
  }

  return stats;
}

const COMPARE_OPTIONS = [
  { value: "current" as const, label: "This year" },
  { value: "yoy" as const, label: "vs Last year" },
];

export function InsightsPage() {
  const { year, month } = useMonthYear();
  const groupIconMap = useGroupIconMap();
  const [compareMode, setCompareMode] = useState<"current" | "yoy">("current");
  const [expandedGroupId, setExpandedGroupId] = useState<string | null>(null);

  const {
    data: response,
    isLoading,
    error,
    refetch,
  } = useGetSpendingTrends({
    year,
    month,
    comparison_year: compareMode === "yoy" ? year - 1 : undefined,
  });
  const data = response?.status === 200 ? response.data : undefined;

  const groupCharts = useMemo(
    () =>
      data
        ? buildGroupCharts(data.monthly_group_spending, data.group_summaries)
        : [],
    [data],
  );

  const comparisonMap = useMemo(
    () =>
      data?.comparison_monthly_group_spending
        ? groupSpendingByGroupId(data.comparison_monthly_group_spending)
        : new Map(),
    [data],
  );

  const categoryMap = useMemo(
    () =>
      data ? buildCategoryMap(data.monthly_group_spending, month) : new Map(),
    [data, month],
  );

  const budgetMap = useMemo(
    () =>
      data ? buildBudgetMap(data.budget_lines) : new Map<string, number>(),
    [data],
  );

  const stats = useMemo(() => (data ? buildStats(data) : []), [data]);

  const { personNames } = usePersonMaps(data?.persons);

  const comparisonCards = data?.comparison_cards ?? [];
  const settlementTrend = data?.settlement_trend ?? [];

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <PageHeader icon={<TrendingUp className="size-6" />} title="Insights">
        <div className="flex items-center gap-2">
          <SegmentedControl
            options={COMPARE_OPTIONS}
            value={compareMode}
            onChange={setCompareMode}
            size="sm"
          />
          <MonthPicker />
          <YearSelector />
        </div>
      </PageHeader>

      {isLoading && <PageLoading label="Loading spending trends..." />}

      {error && <PageError error={error} onRetry={refetch} />}

      {data && groupCharts.length === 0 && (
        <PageEmpty
          icon={<TrendingUp />}
          heading="No spending data"
          description={`No shared expenses found for ${year}. Upload a CSV to get started.`}
        />
      )}

      {data && groupCharts.length > 0 && (
        <div className="space-y-6">
          <StatsGrid stats={stats} />

          {comparisonCards.length > 0 && (
            <section>
              <h2 className="mb-3 text-sm font-medium text-muted-foreground">
                {MONTHS[month - 1]} vs 3-month average
              </h2>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {comparisonCards.map((card) => (
                  <ComparisonCard
                    key={card.group_id ?? "uncategorized"}
                    groupName={card.group_name}
                    groupIcon={groupIconMap.get(card.group_id ?? "") ?? null}
                    currentAmount={card.current_month_amount}
                    trailingAverage={card.trailing_average}
                    deltaAmount={card.delta_amount}
                    deltaPercentage={card.delta_percentage}
                  />
                ))}
              </div>
            </section>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {groupCharts.map((group, index) => (
              <SparklineCard
                key={group.groupId ?? "uncategorized"}
                groupName={group.groupName}
                groupIcon={groupIconMap.get(group.groupId ?? "") ?? null}
                data={group.data}
                ytdTotal={group.ytdTotal}
                color={getChartColor(index)}
                budgetLine={budgetMap.get(group.groupId ?? "") ?? null}
                comparisonData={
                  compareMode === "yoy"
                    ? (comparisonMap.get(group.groupId) ?? undefined)
                    : undefined
                }
                comparisonYear={compareMode === "yoy" ? year - 1 : undefined}
                year={year}
                isExpanded={
                  expandedGroupId === (group.groupId ?? "uncategorized")
                }
                onToggle={() =>
                  setExpandedGroupId(
                    expandedGroupId === (group.groupId ?? "uncategorized")
                      ? null
                      : (group.groupId ?? "uncategorized"),
                  )
                }
                categories={categoryMap.get(group.groupId) ?? undefined}
                selectedMonth={month}
              />
            ))}
          </div>

          <SettlementTrendChart
            data={settlementTrend}
            personNames={personNames}
          />
        </div>
      )}
    </div>
  );
}
