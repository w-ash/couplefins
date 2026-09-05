import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";
import type { TrendPoint } from "@/lib/insights-data";

/** A 36px trend line for a table row: this year solid, last year dashed. */
export function MiniTrendLine({
  trend,
  priorTrend,
  color,
  selectedMonth,
}: {
  trend: TrendPoint[];
  priorTrend: TrendPoint[] | null;
  color: string;
  selectedMonth: number;
}) {
  const data = trend.map((p) => ({
    month: p.month,
    amount: p.month <= selectedMonth ? p.amount : null,
    prior: priorTrend?.find((q) => q.month === p.month)?.amount ?? null,
  }));
  const max = Math.max(
    1,
    ...data.map((d) => Math.max(d.amount ?? 0, d.prior ?? 0)),
  );
  return (
    <ResponsiveContainer width="100%" height={36}>
      <LineChart data={data} margin={{ top: 3, right: 2, bottom: 3, left: 2 }}>
        <YAxis hide domain={[0, max * 1.05]} />
        {priorTrend && (
          <Line
            type="monotone"
            dataKey="prior"
            stroke="var(--color-muted-foreground)"
            strokeWidth={1}
            strokeDasharray="3 2"
            strokeOpacity={0.4}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
        )}
        <Line
          type="monotone"
          dataKey="amount"
          stroke={color}
          strokeWidth={1.75}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
