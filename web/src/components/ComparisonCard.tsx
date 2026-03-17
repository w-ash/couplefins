import { Card } from "@/components/Card";
import { getCategoryGroupIcon } from "@/lib/category-icons";
import { formatCurrency } from "@/lib/format";

interface ComparisonCardProps {
  groupName: string;
  groupIcon: string | null;
  currentAmount: number;
  trailingAverage: number;
  deltaAmount: number;
  deltaPercentage: number;
}

function deltaColorClass(pct: number): string {
  if (pct <= 0) return "text-positive";
  if (pct > 25) return "text-destructive";
  return "text-foreground";
}

export function ComparisonCard({
  groupName,
  groupIcon,
  currentAmount,
  trailingAverage,
  deltaAmount,
  deltaPercentage,
}: ComparisonCardProps) {
  const Icon = getCategoryGroupIcon(groupIcon);
  const sign = deltaAmount >= 0 ? "+" : "";
  const pctSign = deltaPercentage >= 0 ? "+" : "";

  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center gap-2">
        <Icon className="size-4 text-muted-foreground" />
        <span className="text-sm font-medium text-foreground">{groupName}</span>
      </div>
      <div className="flex items-baseline justify-between">
        <div>
          <span className="text-lg font-semibold tabular-nums text-foreground">
            {formatCurrency(currentAmount)}
          </span>
          <span className="ml-2 text-xs text-muted-foreground">
            3-mo avg: {formatCurrency(trailingAverage)}
          </span>
        </div>
        <span
          className={`text-sm font-medium tabular-nums ${deltaColorClass(deltaPercentage)}`}
        >
          {sign}
          {formatCurrency(Math.abs(deltaAmount))} ({pctSign}
          {Math.round(deltaPercentage)}%)
        </span>
      </div>
    </Card>
  );
}
