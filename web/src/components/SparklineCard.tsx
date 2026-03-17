import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/Card";
import { getCategoryGroupIcon } from "@/lib/category-icons";
import { formatCurrency, MONTHS } from "@/lib/format";

interface DataPoint {
  month: number;
  amount: number;
}

interface SparklineCardProps {
  groupName: string;
  groupIcon: string | null;
  data: DataPoint[];
  ytdTotal: number;
  color: string;
}

const SHORT_MONTHS = MONTHS.map((m) => m.slice(0, 3));

function SparklineTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { value: number; payload: DataPoint }[];
}) {
  if (!active || !payload?.[0]) return null;
  const { month } = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-1.5 text-xs shadow-md">
      <span className="text-muted-foreground">{MONTHS[month - 1]}</span>
      <span className="ml-2 font-medium tabular-nums text-foreground">
        {formatCurrency(payload[0].value)}
      </span>
    </div>
  );
}

export function SparklineCard({
  groupName,
  groupIcon,
  data,
  ytdTotal,
  color,
}: SparklineCardProps) {
  const Icon = getCategoryGroupIcon(groupIcon);

  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="size-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">
            {groupName}
          </span>
        </div>
        <span className="text-xs tabular-nums text-muted-foreground">
          YTD: {formatCurrency(ytdTotal)}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart
          data={data}
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
          <YAxis domain={[0, "auto"]} hide />
          <Tooltip content={<SparklineTooltip />} cursor={false} />
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
    </Card>
  );
}
