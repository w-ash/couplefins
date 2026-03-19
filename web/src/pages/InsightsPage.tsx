import { TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, BarChart, ResponsiveContainer } from "recharts";
import { useGetSpendingTrends } from "@/api/generated/insights/insights";
import type {
  BudgetLineItem,
  CategorySpendingItem,
  GroupSummaryItem,
  MonthlyGroupSpendingItem,
  MonthlyPersonPaidItem,
  MonthlySettlementItem,
  SpendingTrendsResponse,
} from "@/api/generated/model";
import { Card } from "@/components/Card";
import { ComparisonCard } from "@/components/ComparisonCard";
import { MonthPicker } from "@/components/MonthPicker";
import { PageHeader } from "@/components/PageHeader";
import { PageEmpty, PageError, PageLoading } from "@/components/PageStates";
import { PersonPaidChart } from "@/components/PersonPaidChart";
import { SettlementTrendChart } from "@/components/SettlementTrendChart";
import { SparklineCard } from "@/components/SparklineCard";
import { useGroupIconMap } from "@/lib/categories";
import { getChartColor } from "@/lib/chart-colors";
import {
  formatCurrency,
  getDeltaColorClass,
  MONTHS,
  useMonthYear,
} from "@/lib/format";
import { PAGE_PADDING } from "@/lib/layout";
import { usePersonMaps } from "@/lib/persons";

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

interface KpiData {
  ytdTotal: number;
  monthCount: number;
  avg: number;
  selectedMonth: { label: string; amount: number };
  selectedDelta: { pct: number; label: string } | null;
  trailingAvg: number | null;
  topGroup: { name: string; amount: number; sharePct: number } | null;
}

function buildKpiData(
  data: SpendingTrendsResponse,
  month: number,
): KpiData | null {
  const { monthly_totals: totals, group_summaries: groups } = data;
  if (totals.length === 0) return null;

  const ytdTotal = groups.reduce((sum, g) => sum + g.ytd_total, 0);
  const monthCount = totals.length;
  const avg = ytdTotal / monthCount;

  const selectedAmount =
    totals.find((t) => t.month === month)?.total_amount ?? 0;

  const trailing = totals
    .filter((t) => t.month < month)
    .sort((a, b) => b.month - a.month)
    .slice(0, 3);
  const trailingAvg =
    trailing.length > 0
      ? trailing.reduce((s, t) => s + t.total_amount, 0) / trailing.length
      : null;
  const selectedDelta =
    trailingAvg != null && trailingAvg > 0
      ? {
          pct: ((selectedAmount - trailingAvg) / trailingAvg) * 100,
          label: "vs 3-mo avg",
        }
      : null;

  const top = groups[0];
  const topGroup =
    top && ytdTotal > 0
      ? {
          name: top.group_name,
          amount: top.ytd_total,
          sharePct: (top.ytd_total / ytdTotal) * 100,
        }
      : null;

  return {
    ytdTotal,
    monthCount,
    avg,
    selectedMonth: { label: MONTHS[month - 1], amount: selectedAmount },
    selectedDelta,
    trailingAvg,
    topGroup,
  };
}

interface PersonPaidChartPoint {
  month: number;
  [personId: string]: number | string;
}

function buildPersonPaidChartData(
  items: MonthlyPersonPaidItem[],
  selectedGroupIds: Set<string> | "all",
): PersonPaidChartPoint[] {
  const byMonth = new Map<number, PersonPaidChartPoint>();

  for (const item of items) {
    if (
      selectedGroupIds !== "all" &&
      !selectedGroupIds.has(item.group_id ?? "")
    )
      continue;

    let point = byMonth.get(item.month);
    if (!point) {
      point = { month: item.month };
      byMonth.set(item.month, point);
    }
    const current = (point[item.person_id] as number) ?? 0;
    point[item.person_id] = current + item.amount_paid;
  }

  return [...byMonth.values()].sort(
    (a, b) => (a.month as number) - (b.month as number),
  );
}

function buildPersonYtdTotals(
  items: MonthlyPersonPaidItem[],
  selectedGroupIds: Set<string> | "all",
): Map<string, number> {
  const totals = new Map<string, number>();
  for (const item of items) {
    if (
      selectedGroupIds !== "all" &&
      !selectedGroupIds.has(item.group_id ?? "")
    )
      continue;
    totals.set(
      item.person_id,
      (totals.get(item.person_id) ?? 0) + item.amount_paid,
    );
  }
  return totals;
}

function buildSettledCount(
  data: MonthlySettlementItem[],
): { settled: number; total: number } | null {
  if (data.length === 0) return null;
  return {
    settled: data.filter((d) => d.is_settled).length,
    total: data.length,
  };
}

function filterPillClass(selected: boolean): string {
  return `rounded-full px-3 py-1 text-xs font-medium transition-colors ${
    selected
      ? "bg-primary text-primary-foreground"
      : "bg-muted text-muted-foreground hover:text-foreground"
  }`;
}

export function InsightsPage() {
  const { year, month } = useMonthYear();
  const groupIconMap = useGroupIconMap();
  const [expandedGroupId, setExpandedGroupId] = useState<string | null>(null);
  const [paidFilterGroups, setPaidFilterGroups] = useState<Set<string> | "all">(
    "all",
  );

  const {
    data: response,
    isLoading,
    error,
    refetch,
  } = useGetSpendingTrends({
    year,
    month,
    comparison_year: year - 1,
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

  const kpi = useMemo(
    () => (data ? buildKpiData(data, month) : null),
    [data, month],
  );

  const sortedMonthlyTotals = useMemo(
    () =>
      data ? [...data.monthly_totals].sort((a, b) => a.month - b.month) : [],
    [data],
  );

  const personPaidItems = useMemo(
    () => data?.monthly_person_paid ?? [],
    [data],
  );

  const personPaidChartData = useMemo(
    () => buildPersonPaidChartData(personPaidItems, paidFilterGroups),
    [personPaidItems, paidFilterGroups],
  );

  const personYtdTotals = useMemo(
    () => buildPersonYtdTotals(personPaidItems, paidFilterGroups),
    [personPaidItems, paidFilterGroups],
  );

  const settledCount = useMemo(
    () => (data ? buildSettledCount(data.settlement_trend) : null),
    [data],
  );

  const { personNames } = usePersonMaps(data?.persons);

  const personChartEntries = useMemo(
    () =>
      (data?.persons ?? []).map((p, i) => ({
        id: p.id,
        name: p.name,
        color: `var(--person-${i})`,
      })),
    [data?.persons],
  );

  const comparisonCards = data?.comparison_cards ?? [];
  const settlementTrend = data?.settlement_trend ?? [];

  return (
    <div className={`mx-auto max-w-4xl ${PAGE_PADDING}`}>
      <PageHeader icon={<TrendingUp className="size-6" />} title="Insights">
        <MonthPicker />
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
          {kpi && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {/* Hero — Year to date */}
              <Card className="rounded-lg p-5">
                <p className="text-sm font-medium text-muted-foreground">
                  Year to date
                </p>
                <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                  {formatCurrency(kpi.ytdTotal)}
                </p>
                {sortedMonthlyTotals.length > 0 && (
                  <div className="mt-3" data-testid="ytd-mini-chart">
                    <ResponsiveContainer width="100%" height={48}>
                      <BarChart
                        data={sortedMonthlyTotals}
                        margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
                      >
                        <Bar
                          dataKey="total_amount"
                          fill="var(--color-primary)"
                          fillOpacity={0.2}
                          radius={[2, 2, 0, 0]}
                          isAnimationActive={false}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
                <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                  averaging {formatCurrency(kpi.avg)}/mo &middot;{" "}
                  {kpi.monthCount} {kpi.monthCount === 1 ? "month" : "months"}
                </p>
              </Card>

              {/* Selected month */}
              <Card className="rounded-lg p-4">
                <p className="text-xs font-medium text-muted-foreground">
                  {kpi.selectedMonth.label}
                </p>
                <p className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                  {formatCurrency(kpi.selectedMonth.amount)}
                </p>
                {kpi.trailingAvg != null && (
                  <div className="mt-2 space-y-1">
                    <div className="h-1 rounded-full bg-muted">
                      <div
                        className="h-1 rounded-full bg-primary"
                        style={{
                          width: `${(kpi.selectedMonth.amount / Math.max(kpi.selectedMonth.amount, kpi.trailingAvg, 1)) * 100}%`,
                        }}
                      />
                    </div>
                    <div className="h-1 rounded-full bg-muted">
                      <div
                        className="h-1 rounded-full bg-muted-foreground/30"
                        style={{
                          width: `${(kpi.trailingAvg / Math.max(kpi.selectedMonth.amount, kpi.trailingAvg, 1)) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
                <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                  {kpi.selectedDelta ? (
                    <span
                      className={`font-medium ${getDeltaColorClass(kpi.selectedDelta.pct)}`}
                    >
                      {kpi.selectedDelta.pct >= 0 ? "+" : ""}
                      {Math.round(kpi.selectedDelta.pct)}%{" "}
                      {kpi.selectedDelta.label}
                    </span>
                  ) : (
                    "First month on record"
                  )}
                </p>
              </Card>

              {/* Top category */}
              <Card className="rounded-lg p-4">
                <p className="text-xs font-medium text-muted-foreground">
                  Top category
                </p>
                <p className="mt-1 text-lg font-semibold text-foreground">
                  {kpi.topGroup?.name ?? "None"}
                </p>
                {kpi.topGroup && (
                  <div className="mt-2">
                    <div className="h-1.5 rounded-full bg-muted">
                      <div
                        className="h-1.5 rounded-full bg-primary"
                        style={{
                          width: `${Math.min(100, Math.round(kpi.topGroup.sharePct))}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
                {kpi.topGroup && (
                  <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                    {formatCurrency(kpi.topGroup.amount)} &mdash;{" "}
                    {Math.round(kpi.topGroup.sharePct)}% of YTD
                  </p>
                )}
              </Card>
            </div>
          )}

          {comparisonCards.length > 0 && (
            <section>
              <h2 className="mb-1 font-medium text-lg text-foreground">
                {MONTHS[month - 1]} vs 3-month average
              </h2>
              <p className="mb-4 text-xs text-muted-foreground">
                Spot categories where spending jumped or dropped this month
              </p>
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

          <section>
            <h2 className="mb-1 font-medium text-lg text-foreground">
              Spending by category
            </h2>
            <p className="mb-4 text-xs text-muted-foreground">
              Monthly trends for each category — tap to see the breakdown
            </p>
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
                  comparisonData={comparisonMap.get(group.groupId) ?? undefined}
                  comparisonYear={year - 1}
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
          </section>

          {(personPaidChartData.length > 0 || settlementTrend.length > 0) && (
            <section>
              <h2 className="mb-1 font-medium text-lg text-foreground">
                Who's paying
              </h2>
              <p className="mb-4 text-xs text-muted-foreground">
                See who's been covering more of the shared spending each month
              </p>

              {/* Category group filter */}
              {data && data.group_summaries.length > 1 && (
                <div className="mb-4 flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => setPaidFilterGroups("all")}
                    className={filterPillClass(paidFilterGroups === "all")}
                  >
                    All categories
                  </button>
                  {data.group_summaries.map((gs) => {
                    const gid = gs.group_id ?? "";
                    const isSelected =
                      paidFilterGroups !== "all" && paidFilterGroups.has(gid);
                    return (
                      <button
                        key={gid}
                        type="button"
                        onClick={() => {
                          setPaidFilterGroups((prev) => {
                            if (prev === "all") return new Set([gid]);
                            const next = new Set(prev);
                            if (next.has(gid)) next.delete(gid);
                            else next.add(gid);
                            return next.size === 0 ? "all" : next;
                          });
                        }}
                        className={filterPillClass(isSelected)}
                      >
                        {gs.group_name}
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Per-person stats */}
              <div className="mb-4 grid grid-cols-3 gap-3">
                {personChartEntries.map((person) => (
                  <Card key={person.id} className="rounded-lg p-4">
                    <p className="text-xs font-medium text-muted-foreground">
                      {person.name} paid
                    </p>
                    <p className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                      {formatCurrency(personYtdTotals.get(person.id) ?? 0)}
                    </p>
                  </Card>
                ))}
                {settledCount && (
                  <Card className="rounded-lg p-4">
                    <p className="text-xs font-medium text-muted-foreground">
                      Months settled
                    </p>
                    <p className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                      {settledCount.settled} of {settledCount.total}
                    </p>
                  </Card>
                )}
              </div>

              {/* Who's paying chart */}
              <PersonPaidChart
                data={personPaidChartData}
                persons={personChartEntries}
              />

              {/* Settlement trend */}
              {settlementTrend.length > 0 && (
                <div className="mt-4">
                  <SettlementTrendChart
                    data={settlementTrend}
                    personNames={personNames}
                  />
                </div>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  );
}
