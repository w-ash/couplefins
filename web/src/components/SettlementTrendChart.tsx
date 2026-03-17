import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MonthlySettlementItem } from "@/api/generated/model";
import { Card } from "@/components/Card";
import { getChartColor } from "@/lib/chart-colors";
import { formatCurrency, MONTHS, SHORT_MONTHS } from "@/lib/format";

interface SettlementTrendChartProps {
  data: MonthlySettlementItem[];
  personNames: Map<string, string>;
}

interface ChartPoint {
  month: number;
  amount: number;
  fromName: string;
  toName: string;
  isSettled: boolean;
}

function SettlementTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: ChartPoint }[];
}) {
  if (!active || !payload?.[0]) return null;
  const pt = payload[0].payload;
  const status = pt.isSettled ? "settled" : "unsettled";
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="text-muted-foreground">{MONTHS[pt.month - 1]}</div>
      <div className="mt-0.5 font-medium text-foreground">
        {pt.fromName} owes {pt.toName} {formatCurrency(Math.abs(pt.amount))}
      </div>
      <div className="text-muted-foreground">({status})</div>
    </div>
  );
}

function SettlementDot(props: {
  cx?: number;
  cy?: number;
  payload?: ChartPoint;
}) {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null || !payload) return null;
  const color = getChartColor(0);
  if (payload.isSettled) {
    return <circle cx={cx} cy={cy} r={4} fill={color} stroke="none" />;
  }
  return (
    <circle
      cx={cx}
      cy={cy}
      r={4}
      fill="var(--color-card)"
      stroke={color}
      strokeWidth={1.5}
    />
  );
}

export function SettlementTrendChart({
  data,
  personNames,
}: SettlementTrendChartProps) {
  if (data.length === 0) return null;

  // Pick first person as reference for directionality
  const refPersonId = data[0].from_person_id;

  const chartData: ChartPoint[] = data.map((d) => {
    const directedAmount =
      d.from_person_id === refPersonId ? d.amount : -d.amount;
    return {
      month: d.month,
      amount: directedAmount,
      fromName: personNames.get(d.from_person_id) ?? "Unknown",
      toName: personNames.get(d.to_person_id) ?? "Unknown",
      isSettled: d.is_settled,
    };
  });

  return (
    <Card as="section" className="p-6">
      <h2 className="mb-4 text-sm font-medium text-foreground">
        Settlement Balance
      </h2>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart
          data={chartData}
          margin={{ top: 8, right: 16, bottom: 0, left: 16 }}
        >
          <XAxis
            dataKey="month"
            tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(m: number) => SHORT_MONTHS[m - 1]}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => formatCurrency(Math.abs(v))}
            width={60}
          />
          <ReferenceLine y={0} stroke="var(--color-border)" strokeWidth={1} />
          <Tooltip content={<SettlementTooltip />} cursor={false} />
          <Line
            type="monotone"
            dataKey="amount"
            stroke={getChartColor(0)}
            strokeWidth={2}
            dot={<SettlementDot />}
            activeDot={{ r: 5, fill: getChartColor(0) }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
