import { TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { Bar, BarChart, ResponsiveContainer } from "recharts";
import { useGetSpendingTrends } from "@/api/generated/insights/insights";
import { Card } from "@/components/Card";
import { GroupBreakdownTable } from "@/components/insights/GroupBreakdownTable";
import { MonthlyStackChart } from "@/components/insights/MonthlyStackChart";
import { NotableList } from "@/components/insights/NotableList";
import { SpendingBars } from "@/components/insights/SpendingBars";
import { SpendingDonut } from "@/components/insights/SpendingDonut";
import { SpendingFlowChart } from "@/components/insights/SpendingFlowChart";
import { SpendingLegendTable } from "@/components/insights/SpendingLegendTable";
import { MonthPicker } from "@/components/MonthPicker";
import { PageHeader } from "@/components/PageHeader";
import { PageEmpty, PageError, PageLoading } from "@/components/PageStates";
import { SectionHeader } from "@/components/SectionHeader";
import { SegmentedControl } from "@/components/SegmentedControl";
import { useGroupIconMap } from "@/lib/categories";
import {
  formatCurrency,
  getDeltaColorClass,
  MONTHS,
  useMonthYearParams,
  useResolvedPeriod,
} from "@/lib/format";
import { useIdentityStore } from "@/lib/identity";
import {
  buildGroupRows,
  buildHeadline,
  buildMonthlyStack,
  buildNotable,
} from "@/lib/insights-data";
import {
  INSIGHTS_CHART_OPTIONS,
  INSIGHTS_GROUP_BY_OPTIONS,
  INSIGHTS_PERIOD_OPTIONS,
  type InsightsChart,
  type InsightsGroupBy,
  type InsightsPeriod,
  periodRange,
  useInsightsFilters,
} from "@/lib/insights-filters";
import { PAGE_PADDING } from "@/lib/layout";
import { PERSON_SCOPE_OPTIONS, type PersonScope } from "@/lib/person-scope";
import { usePersonMaps } from "@/lib/persons";
import {
  assignGroupColors,
  buildCategorySlices,
  buildGroupSlices,
  buildMerchantSlices,
  buildSankeyData,
  type FlowContext,
  foldSlices,
  type SliceDatum,
} from "@/lib/spending-flow";

const EMPTY_ICON_MAP = new Map<string, string | null>();

export function InsightsPage() {
  const { year: urlYear, month: urlMonth } = useMonthYearParams();
  const [, setSearchParams] = useSearchParams();
  const {
    scope,
    setScope,
    period,
    setPeriod,
    chart,
    setChart,
    groupBy,
    setGroupBy,
  } = useInsightsFilters();
  const isPersonal = scope === "personal";
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const groupIconMap = useGroupIconMap();
  const [drill, setDrill] = useState<{ key: string; name: string } | null>(
    null,
  );

  const {
    data: response,
    isLoading,
    error,
    refetch,
    // A URL without a month asks for the default view: the server answers
    // with the latest month that has spending. The comparison year is the
    // server's to pick — always the year before the one it resolved.
  } = useGetSpendingTrends({ year: urlYear, month: urlMonth, scope });
  const data = response?.status === 200 ? response.data : undefined;
  const { year, month, pickerValue } = useResolvedPeriod(data);
  const { personNames, personIndexMap } = usePersonMaps(data?.persons);

  // A drill-down belongs to one view; leave it when the view changes.
  const drillKey = `${year}-${month}-${scope}-${period}-${groupBy}`;
  const [lastDrillKey, setLastDrillKey] = useState(drillKey);
  if (lastDrillKey !== drillKey) {
    setLastDrillKey(drillKey);
    setDrill(null);
  }

  const ctx: FlowContext = useMemo(
    () => ({
      range: periodRange(year, month, period),
      scope,
      currentPersonId,
      personNames,
      personIndex: personIndexMap,
      groupColors: assignGroupColors(
        (data?.group_summaries ?? []).map((g) => g.group_id),
      ),
    }),
    [
      year,
      month,
      period,
      scope,
      currentPersonId,
      personNames,
      personIndexMap,
      data?.group_summaries,
    ],
  );

  const flow = data
    ? period === "month"
      ? data.month_flow
      : data.ytd_flow
    : null;
  const headline = useMemo(
    () => (data ? buildHeadline(data, period) : null),
    [data, period],
  );
  const sankey = useMemo(
    () => (flow ? buildSankeyData(flow.cells, ctx) : null),
    [flow, ctx],
  );
  const slices = useMemo<SliceDatum[]>(() => {
    if (!flow) return [];
    if (groupBy === "merchant")
      return buildMerchantSlices(flow.top_merchants, ctx);
    if (groupBy === "category")
      return foldSlices(buildCategorySlices(flow.cells, ctx), ctx);
    if (drill)
      return foldSlices(buildCategorySlices(flow.cells, ctx, drill.key), ctx);
    return buildGroupSlices(flow.cells, ctx);
  }, [flow, ctx, groupBy, drill]);
  const stack = useMemo(
    () => (data ? buildMonthlyStack(data, ctx) : null),
    [data, ctx],
  );
  const groupRows = useMemo(
    () => (data ? buildGroupRows(data, period, ctx) : []),
    [data, period, ctx],
  );
  const notable = useMemo(
    () => (data && period === "month" ? buildNotable(data, ctx) : []),
    [data, period, ctx],
  );

  const sortedMonthlyTotals = useMemo(
    () =>
      data ? [...data.monthly_totals].sort((a, b) => a.month - b.month) : [],
    [data],
  );

  const canDrill = (slice: SliceDatum) =>
    groupBy === "group" && !drill && slice.groupKey !== null && !slice.members;
  const onDrill = (slice: SliceDatum) =>
    setDrill({ key: slice.groupKey ?? "", name: slice.name });
  const selectMonth = (m: number) =>
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("year", String(year));
      next.set("month", String(m));
      return next;
    });

  const hasYearData = (data?.group_summaries.length ?? 0) > 0;
  const hasPeriodData = (flow?.cells.length ?? 0) > 0;
  const sliceTotal = slices.reduce((s, x) => s + x.amount, 0);

  return (
    <div className={`mx-auto max-w-5xl ${PAGE_PADDING}`}>
      <PageHeader icon={<TrendingUp className="size-6" />} title="Insights">
        <MonthPicker value={pickerValue} />
      </PageHeader>

      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3">
        <SegmentedControl<PersonScope>
          options={PERSON_SCOPE_OPTIONS}
          value={scope}
          onChange={setScope}
          size="sm"
        />
        <SegmentedControl<InsightsPeriod>
          options={INSIGHTS_PERIOD_OPTIONS}
          value={period}
          onChange={setPeriod}
          size="sm"
        />
        {isPersonal && (
          <p className="text-xs text-muted-foreground">
            Your share of household spending, your personal spending, and what
            your partner spotted for you
          </p>
        )}
      </div>

      {isLoading && <PageLoading label="Loading spending insights..." />}

      {error && <PageError error={error} onRetry={refetch} />}

      {data && !hasYearData && (
        <PageEmpty
          icon={<TrendingUp />}
          heading="No spending data"
          description={
            isPersonal
              ? `No spending of yours found for ${year}. Upload a CSV to get started.`
              : `No household expenses found for ${year}. Upload a CSV to get started.`
          }
        />
      )}

      {data && hasYearData && headline && (
        <div className="space-y-8">
          <Card className="flex flex-col gap-4 rounded-lg p-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                {headline.label}
              </p>
              <p className="mt-1 text-3xl font-semibold tabular-nums text-foreground">
                {formatCurrency(headline.total)}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {headline.comparison ? (
                  <span
                    className={`font-medium ${getDeltaColorClass(headline.comparison.deltaPct)}`}
                  >
                    {formatCurrency(Math.abs(headline.comparison.deltaAmount))}{" "}
                    {headline.comparison.text}
                  </span>
                ) : (
                  "First period on record"
                )}
              </p>
            </div>
            {sortedMonthlyTotals.length > 0 && (
              <div className="w-full sm:w-64" data-testid="ytd-mini-chart">
                <ResponsiveContainer width="100%" height={44}>
                  <BarChart
                    data={sortedMonthlyTotals}
                    margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
                  >
                    <Bar
                      dataKey="total_amount"
                      fill="var(--color-primary)"
                      fillOpacity={0.3}
                      radius={[2, 2, 0, 0]}
                      isAnimationActive={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>

          <section aria-labelledby="where-heading">
            <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <SectionHeader
                  id="where-heading"
                  title="Where the money went"
                  description="Click any part of the chart or the legend to see its transactions"
                />
              </div>
              {/* The chart selector stays put on the right; the group-by
                  control appears to its left only when the chart uses it. */}
              <div className="mb-4 flex flex-wrap justify-end gap-2">
                {chart !== "flow" && (
                  <SegmentedControl<InsightsGroupBy>
                    options={INSIGHTS_GROUP_BY_OPTIONS}
                    value={groupBy}
                    onChange={setGroupBy}
                    size="sm"
                  />
                )}
                <SegmentedControl<InsightsChart>
                  options={INSIGHTS_CHART_OPTIONS}
                  value={chart}
                  onChange={setChart}
                  size="sm"
                />
              </div>
            </div>
            {!hasPeriodData ? (
              <Card className="rounded-lg p-5 text-sm text-muted-foreground">
                No spending in {headline.label}. Pick another month or switch to
                year to date.
              </Card>
            ) : chart === "flow" && sankey ? (
              <Card className="rounded-lg p-4">
                <p className="mb-2 text-xs text-muted-foreground sm:hidden">
                  Swipe sideways to see the whole flow, or switch to Bars.
                </p>
                <SpendingFlowChart dataset={sankey} />
                {sankey.droppedRefundOnly > 0 && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {sankey.droppedRefundOnly} refund-heavy{" "}
                    {sankey.droppedRefundOnly === 1 ? "line is" : "lines are"}{" "}
                    left out of the flow; the table below still counts{" "}
                    {sankey.droppedRefundOnly === 1 ? "it" : "them"}.
                  </p>
                )}
              </Card>
            ) : chart === "donut" ? (
              <Card className="rounded-lg p-4">
                <div className="grid gap-4 lg:grid-cols-[280px_1fr] lg:items-start">
                  <SpendingDonut
                    slices={slices}
                    centerLabel={drill ? drill.name : headline.label}
                    total={sliceTotal}
                    canDrill={canDrill}
                    onDrill={onDrill}
                  />
                  <SpendingLegendTable
                    slices={slices}
                    breadcrumb={
                      drill
                        ? { label: drill.name, onBack: () => setDrill(null) }
                        : null
                    }
                    canDrill={canDrill}
                    onDrill={onDrill}
                  />
                </div>
              </Card>
            ) : (
              <Card className="rounded-lg p-4">
                {drill && (
                  <nav
                    aria-label="Breakdown level"
                    className="mb-3 flex items-center gap-1 text-xs"
                  >
                    <button
                      type="button"
                      onClick={() => setDrill(null)}
                      className="text-primary hover:underline"
                    >
                      All groups
                    </button>
                    <span className="text-muted-foreground">›</span>
                    <span className="font-medium text-foreground">
                      {drill.name}
                    </span>
                  </nav>
                )}
                <SpendingBars
                  slices={slices}
                  canDrill={canDrill}
                  onDrill={onDrill}
                />
              </Card>
            )}
          </section>

          <section aria-labelledby="time-heading">
            <SectionHeader
              id="time-heading"
              title="Spending over time"
              description={`Each bar is a month of ${year}; the dotted line is ${year - 1}. Click a bar to select that month.`}
            />
            <Card className="rounded-lg p-4">
              {stack && (
                <MonthlyStackChart
                  stack={stack}
                  year={year}
                  selectedMonth={month}
                  onSelectMonth={selectMonth}
                />
              )}
              <div className="mt-4 border-t border-border-muted pt-3">
                <GroupBreakdownTable
                  rows={groupRows}
                  iconMap={groupIconMap ?? EMPTY_ICON_MAP}
                  selectedMonth={month}
                />
              </div>
            </Card>
          </section>

          {notable.length > 0 && (
            <section aria-labelledby="notable-heading">
              <SectionHeader
                id="notable-heading"
                title={`Notable in ${MONTHS[month - 1]}`}
                description="The biggest swings against the last three months"
              />
              <Card className="rounded-lg px-4 py-1">
                <NotableList items={notable} />
              </Card>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
