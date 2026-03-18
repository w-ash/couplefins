import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import type { ReactNode } from "react";
import { useMemo } from "react";
import { Link } from "react-router";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/Card";
import { getCategoryGroupIcon } from "@/lib/category-icons";
import { formatCurrency, MONTHS, SHORT_MONTHS } from "@/lib/format";

interface DataPoint {
  month: number;
  amount: number;
}

interface MergedPoint {
  month: number;
  amount: number;
  comparisonAmount?: number;
}

interface CategoryDetail {
  category: string;
  amount: number;
}

interface SparklineCardProps {
  groupName: string;
  groupIcon: string | null;
  data: DataPoint[];
  ytdTotal: number;
  color: string;
  budgetLine?: number | null;
  comparisonData?: DataPoint[];
  comparisonYear?: number;
  year?: number;
  isExpanded?: boolean;
  onToggle?: () => void;
  categories?: CategoryDetail[];
  selectedMonth?: number;
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
    </div>
  );
}

export function SparklineCard({
  groupName,
  groupIcon,
  data,
  ytdTotal,
  color,
  budgetLine,
  comparisonData,
  comparisonYear,
  year,
  isExpanded,
  onToggle,
  categories,
  selectedMonth,
}: SparklineCardProps) {
  const Icon = getCategoryGroupIcon(groupIcon);
  const budget = budgetLine ?? 0;
  const creep = useMemo(() => detectCreep(data), [data]);
  const isExpandable = onToggle != null;

  const chartData: MergedPoint[] = useMemo(() => {
    if (!comparisonData?.length) return data;
    const compMap = new Map(comparisonData.map((d) => [d.month, d.amount]));
    const allMonths = new Set([
      ...data.map((d) => d.month),
      ...comparisonData.map((d) => d.month),
    ]);
    return [...allMonths]
      .sort((a, b) => a - b)
      .map((month) => ({
        month,
        amount: data.find((d) => d.month === month)?.amount ?? 0,
        comparisonAmount: compMap.get(month),
      }));
  }, [data, comparisonData]);

  const maxComparisonAmount = comparisonData?.length
    ? Math.max(...comparisonData.map((d) => d.amount))
    : 0;

  const headerContent: ReactNode = (
    <>
      <div className="flex items-center gap-2">
        {isExpandable && (
          <span className="shrink-0">
            {isExpanded ? (
              <ChevronDown className="size-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="size-4 text-muted-foreground" />
            )}
          </span>
        )}
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
            margin={{ top: 4, right: 4, bottom: 0, left: 4 }}
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
                  Math.max(dataMax, budget, maxComparisonAmount) * 1.05 || 1,
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
            {budgetLine != null && (
              <ReferenceLine
                y={budgetLine}
                stroke="var(--color-muted-foreground)"
                strokeDasharray="4 4"
                strokeWidth={1}
                label={{
                  value: formatCurrency(budgetLine),
                  position: "right",
                  fontSize: 9,
                  fill: "var(--color-muted-foreground)",
                }}
              />
            )}
            {comparisonData?.length ? (
              <Line
                type="monotone"
                dataKey="comparisonAmount"
                stroke={color}
                strokeWidth={1.5}
                strokeDasharray="6 3"
                strokeOpacity={0.4}
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
              to={`/transactions?year=${year}&month=${selectedMonth}`}
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
