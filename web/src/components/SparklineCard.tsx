import { ArrowRight, TrendingDown, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo } from "react";
import { Link } from "react-router";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/Card";
import { ExpandChevron } from "@/components/ExpandChevron";
import { getCategoryGroupIcon } from "@/lib/category-icons";
import { formatCurrency, MONTHS, SHORT_MONTHS } from "@/lib/format";
import type { PersonScope } from "@/lib/person-scope";

interface DataPoint {
  month: number;
  amount: number;
}

interface MergedPoint {
  month: number;
  amount: number;
  comparisonAmount?: number;
  budgetAmount?: number;
}

interface CategoryDetail {
  category: string;
  amount: number;
}

function transactionsParams(
  year: number,
  month: number,
  scope: PersonScope | undefined,
): string {
  const params = new URLSearchParams({
    year: String(year),
    month: String(month),
  });
  if (scope && scope !== "household") params.set("scope", scope);
  return params.toString();
}

interface SparklineCardProps {
  groupName: string;
  groupIcon: string | null;
  data: DataPoint[];
  ytdTotal: number;
  color: string;
  budgetAmounts?: Array<{ month: number; amount: number }>;
  comparisonData?: DataPoint[];
  comparisonYear?: number;
  year?: number;
  isExpanded?: boolean;
  onToggle?: () => void;
  categories?: CategoryDetail[];
  selectedMonth?: number;
  /** Carries the page's scope into the Transactions drill-down. */
  scope?: PersonScope;
}

function detectCreep(
  data: DataPoint[],
): { direction: "up" | "down"; months: number } | null {
  if (data.length < 4) return null;
  const sorted = [...data].sort((a, b) => a.month - b.month);

  let upStreak = 0;
  for (let i = sorted.length - 1; i > 0; i--) {
    const prev = sorted[i - 1].amount;
    const curr = sorted[i].amount;
    if (prev <= 0) break;
    if (((curr - prev) / Math.abs(prev)) * 100 >= 5) upStreak++;
    else break;
  }
  if (upStreak >= 3) return { direction: "up", months: upStreak };

  let downStreak = 0;
  for (let i = sorted.length - 1; i > 0; i--) {
    const prev = sorted[i - 1].amount;
    const curr = sorted[i].amount;
    if (prev <= 0) break;
    if (((curr - prev) / Math.abs(prev)) * 100 <= -5) downStreak++;
    else break;
  }
  if (downStreak >= 3) return { direction: "down", months: downStreak };

  return null;
}

function SparklineTooltip({
  active,
  payload,
  comparisonYear,
  currentYear,
}: {
  active?: boolean;
  payload?: { value: number; payload: MergedPoint; dataKey: string }[];
  comparisonYear?: number;
  currentYear?: number;
}) {
  if (!active || !payload?.[0]) return null;
  const { month, comparisonAmount } = payload[0].payload;
  const currentAmount = payload[0].payload.amount;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-1.5 text-xs shadow-md">
      <div>
        <span className="text-muted-foreground">
          {MONTHS[month - 1]}
          {currentYear ? ` ${currentYear}` : ""}
        </span>
        <span className="ml-2 font-medium tabular-nums text-foreground">
          {formatCurrency(currentAmount)}
        </span>
      </div>
      {comparisonAmount != null && comparisonYear && (
        <div className="mt-0.5 opacity-60">
          <span className="text-muted-foreground">
            {MONTHS[month - 1]} {comparisonYear}
          </span>
          <span className="ml-2 tabular-nums text-foreground">
            {formatCurrency(comparisonAmount)}
          </span>
        </div>
      )}
      {payload[0].payload.budgetAmount != null && (
        <div className="mt-0.5 opacity-60">
          <span className="text-muted-foreground">Budget</span>
          <span className="ml-2 tabular-nums text-foreground">
            {formatCurrency(payload[0].payload.budgetAmount)}
          </span>
        </div>
      )}
    </div>
  );
}

export function SparklineCard({
  groupName,
  groupIcon,
  data,
  ytdTotal,
  color,
  budgetAmounts,
  comparisonData,
  comparisonYear,
  year,
  isExpanded,
  onToggle,
  categories,
  selectedMonth,
  scope,
}: SparklineCardProps) {
  const Icon = getCategoryGroupIcon(groupIcon);
  const maxBudgetAmount = budgetAmounts?.length
    ? Math.max(...budgetAmounts.map((b) => b.amount))
    : 0;
  const creep = useMemo(() => detectCreep(data), [data]);
  const isExpandable = onToggle != null;

  const chartData: MergedPoint[] = useMemo(() => {
    const dataMap = new Map(data.map((d) => [d.month, d.amount]));
    const compMap = comparisonData?.length
      ? new Map(comparisonData.map((d) => [d.month, d.amount]))
      : null;
    const budgetByMonth = budgetAmounts?.length
      ? new Map(budgetAmounts.map((b) => [b.month, b.amount]))
      : null;
    return Array.from({ length: 12 }, (_, i) => i + 1).map((month) => ({
      month,
      amount: dataMap.get(month) ?? 0,
      comparisonAmount: compMap?.get(month),
      budgetAmount: budgetByMonth?.get(month),
    }));
  }, [data, comparisonData, budgetAmounts]);

  const maxComparisonAmount = comparisonData?.length
    ? Math.max(...comparisonData.map((d) => d.amount))
    : 0;

  const headerContent: ReactNode = (
    <>
      <div className="flex items-center gap-2">
        {isExpandable && <ExpandChevron expanded={isExpanded ?? false} />}
        <Icon className="size-4 text-muted-foreground" />
        <span className="text-sm font-medium text-foreground">{groupName}</span>
        {creep && (
          <span
            className="text-muted-foreground"
            title={`Spending has ${creep.direction === "up" ? "increased" : "decreased"} for ${creep.months} consecutive months`}
          >
            {creep.direction === "up" ? (
              <TrendingUp className="size-3" />
            ) : (
              <TrendingDown className="size-3" />
            )}
          </span>
        )}
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">
        YTD: {formatCurrency(ytdTotal)}
      </span>
    </>
  );

  return (
    <Card className={isExpandable ? "p-0" : "p-4"}>
      {isExpandable ? (
        <button
          type="button"
          className="flex w-full cursor-pointer items-center justify-between px-4 pt-4 pb-2 text-left"
          aria-expanded={isExpanded}
          onClick={onToggle}
        >
          {headerContent}
        </button>
      ) : (
        <div className="mb-2 flex items-center justify-between">
          {headerContent}
        </div>
      )}
      <div className={isExpandable ? "px-4 pb-4" : ""}>
        <ResponsiveContainer width="100%" height={120}>
          <LineChart
            data={chartData}
            margin={{ top: 4, right: 4, bottom: 0, left: 8 }}
          >
            <XAxis
              dataKey="month"
              tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(m: number) =>
                m % 2 === 1 ? SHORT_MONTHS[m - 1] : ""
              }
              interval={0}
            />
            <YAxis
              domain={[
                0,
                (dataMax: number) =>
                  Math.max(dataMax, maxBudgetAmount, maxComparisonAmount) *
                    1.05 || 1,
              ]}
              hide
            />
            <Tooltip
              content={
                <SparklineTooltip
                  comparisonYear={comparisonYear}
                  currentYear={comparisonYear ? year : undefined}
                />
              }
              cursor={false}
            />
            {budgetAmounts?.length ? (
              <Line
                type="stepAfter"
                dataKey="budgetAmount"
                stroke="var(--color-muted-foreground)"
                strokeWidth={1}
                strokeDasharray="4 4"
                strokeOpacity={0.5}
                dot={false}
                activeDot={false}
                connectNulls={false}
              />
            ) : null}
            {comparisonData?.length ? (
              <Line
                type="monotone"
                dataKey="comparisonAmount"
                stroke="var(--color-muted-foreground)"
                strokeWidth={1.5}
                strokeDasharray="4 3"
                strokeOpacity={0.35}
                dot={false}
                activeDot={false}
                connectNulls
              />
            ) : null}
            <Line
              type="monotone"
              dataKey="amount"
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: color }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {isExpanded && categories && categories.length > 0 && (
        <div className="border-t border-border-muted px-4 py-3">
          <div className="space-y-1.5">
            {categories.map((cat) => (
              <div key={cat.category} className="flex justify-between text-sm">
                <span className="text-muted-foreground">{cat.category}</span>
                <span className="tabular-nums text-foreground">
                  {formatCurrency(cat.amount)}
                </span>
              </div>
            ))}
          </div>
          {year && selectedMonth && (
            <Link
              to={`/transactions?${transactionsParams(year, selectedMonth, scope)}`}
              className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              View transactions <ArrowRight className="size-3" />
            </Link>
          )}
        </div>
      )}
    </Card>
  );
}
