import {
  Bar,
  BarChart,
  Cell,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatCurrency, MONTHS } from "@/lib/format";
import type { MonthlyStack, StackRow } from "@/lib/insights-data";
import { ChartTooltipRow, ChartTooltipShell } from "./chart-tooltip";

function StackTooltip({
  active,
  payload,
  stack,
  year,
}: {
  active?: boolean;
  payload?: Array<{ payload?: unknown }>;
  stack: MonthlyStack;
  year: number;
}) {
  const row = payload?.[0]?.payload as StackRow | undefined;
  if (!active || !row) return null;
  const segments = stack.series
    .map((s) => ({ ...s, amount: Number(row[s.key] ?? 0) }))
    .filter((s) => s.amount > 0)
    .sort((a, b) => b.amount - a.amount);
  return (
    <ChartTooltipShell>
      <ChartTooltipRow
        label={`${MONTHS[row.month - 1]} ${year}`}
        value={formatCurrency(row.total)}
      />
      {segments.map((s) => (
        <ChartTooltipRow
          key={s.key}
          label={s.name}
          value={formatCurrency(s.amount)}
          swatch={s.color}
          muted
        />
      ))}
      {row.priorYearTotal != null && row.priorYearTotal > 0 && (
        <ChartTooltipRow
          label={`${MONTHS[row.month - 1]} ${year - 1}`}
          value={formatCurrency(row.priorYearTotal)}
          muted
        />
      )}
    </ChartTooltipShell>
  );
}

/** One stacked bar per month, a segment per group, the prior year as a
 * dotted line; the selected month is drawn at full strength. Clicking a bar
 * selects that month. */
export function MonthlyStackChart({
  stack,
  year,
  selectedMonth,
  onSelectMonth,
  height = 220,
}: {
  stack: MonthlyStack;
  year: number;
  selectedMonth: number;
  onSelectMonth: (month: number) => void;
  height?: number;
}) {
  const hasPrior = stack.rows.some((r) => (r.priorYearTotal ?? 0) > 0);
  const Chart = hasPrior ? ComposedChart : BarChart;
  return (
    <div
      data-testid="monthly-stack-chart"
      role="img"
      aria-label={`Monthly spending in ${year} by category group`}
    >
      <ResponsiveContainer width="100%" height={height}>
        <Chart
          data={stack.rows}
          margin={{ top: 8, right: 4, bottom: 0, left: 4 }}
          barCategoryGap="22%"
          onClick={(state) => {
            const index = state?.activeTooltipIndex;
            const row =
              typeof index === "number" ? stack.rows[index] : undefined;
            if (row) onSelectMonth(row.month);
          }}
        >
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }}
            tickLine={false}
            axisLine={false}
            interval={0}
          />
          <YAxis hide domain={[0, "auto"]} />
          <Tooltip
            cursor={{ fill: "var(--color-muted)", fillOpacity: 0.4 }}
            content={<StackTooltip stack={stack} year={year} />}
          />
          {stack.series.map((s, i) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              stackId="spend"
              fill={s.color}
              isAnimationActive={false}
              radius={i === stack.series.length - 1 ? [3, 3, 0, 0] : 0}
              className="cursor-pointer"
            >
              {stack.rows.map((row) => (
                <Cell
                  key={row.month}
                  fillOpacity={row.month === selectedMonth ? 1 : 0.55}
                />
              ))}
            </Bar>
          ))}
          {hasPrior && (
            <Line
              type="monotone"
              dataKey="priorYearTotal"
              stroke="var(--color-muted-foreground)"
              strokeWidth={1.5}
              strokeDasharray="3 3"
              dot={false}
              activeDot={false}
              isAnimationActive={false}
            />
          )}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}
