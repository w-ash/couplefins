import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/Card";
import { formatCurrency, SHORT_MONTHS } from "@/lib/format";

interface ChartPoint {
  month: number;
  [personId: string]: number | string;
}

interface PersonPaidChartProps {
  data: ChartPoint[];
  persons: { id: string; name: string; color: string }[];
}

function PaidTooltip({
  active,
  payload,
  label,
  persons,
}: {
  active?: boolean;
  payload?: { dataKey: string; value: number }[];
  label?: number;
  persons: { id: string; name: string; color: string }[];
}) {
  if (!active || !payload?.length || label == null) return null;
  const personMap = new Map(persons.map((p) => [p.id, p]));
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <div className="mb-1 text-muted-foreground">
        {SHORT_MONTHS[label - 1]}
      </div>
      {payload.map((entry) => {
        const person = personMap.get(entry.dataKey);
        if (!person) return null;
        return (
          <div key={entry.dataKey} className="flex items-center gap-2">
            <span
              className="inline-block size-2 rounded-full"
              style={{ backgroundColor: person.color }}
            />
            <span className="text-foreground">{person.name}</span>
            <span className="ml-auto tabular-nums font-medium text-foreground">
              {formatCurrency(entry.value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function PersonPaidChart({ data, persons }: PersonPaidChartProps) {
  if (data.length === 0) return null;

  return (
    <Card className="p-6">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart
          data={data}
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
            tickFormatter={(v: number) => formatCurrency(v)}
            width={60}
          />
          <Tooltip content={<PaidTooltip persons={persons} />} cursor={false} />
          {persons.map((person) => (
            <Bar
              key={person.id}
              dataKey={person.id}
              fill={person.color}
              radius={[2, 2, 0, 0]}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
