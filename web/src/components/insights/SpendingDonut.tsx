import { useNavigate } from "react-router";
import {
  Cell,
  Pie,
  PieChart,
  type PieSectorDataItem,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { formatCurrency } from "@/lib/format";
import type { SliceDatum } from "@/lib/spending-flow";
import { buildTransactionsUrl } from "@/lib/transaction-links";
import { ChartTooltipRow, ChartTooltipShell } from "./chart-tooltip";

function DonutTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload?: unknown }>;
}) {
  const slice = payload?.[0]?.payload as SliceDatum | undefined;
  if (!active || !slice) return null;
  return (
    <ChartTooltipShell>
      <ChartTooltipRow
        label={slice.name}
        value={formatCurrency(slice.amount)}
        swatch={slice.color}
      />
      <p className="mt-0.5 text-muted-foreground">
        {Math.round(slice.share * 100)}% · {slice.transactionCount} transactions
      </p>
    </ChartTooltipShell>
  );
}

export function SpendingDonut({
  slices,
  centerLabel,
  total,
  canDrill,
  onDrill,
  height = 280,
}: {
  slices: SliceDatum[];
  centerLabel: string;
  total: number;
  /** A slice that can drill opens its breakdown instead of navigating. */
  canDrill?: (slice: SliceDatum) => boolean;
  onDrill?: (slice: SliceDatum) => void;
  height?: number;
}) {
  const navigate = useNavigate();
  const handleClick = (item: PieSectorDataItem) => {
    const slice = item.payload as SliceDatum | undefined;
    if (!slice) return;
    if (canDrill?.(slice) && onDrill) onDrill(slice);
    else navigate(buildTransactionsUrl(slice.link));
  };

  return (
    <div
      data-testid="spending-donut"
      role="img"
      aria-label={`${centerLabel}: ${formatCurrency(total)} split by ${slices.length} slices`}
      className="relative"
    >
      {/* The center total is HTML, so it keeps the page's type and spacing. */}
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="text-lg font-semibold tabular-nums text-foreground">
          {formatCurrency(total)}
        </span>
        <span className="max-w-[45%] truncate text-[11px] text-muted-foreground">
          {centerLabel}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <PieChart margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <Pie
            data={slices}
            dataKey="amount"
            nameKey="name"
            innerRadius="62%"
            outerRadius="100%"
            paddingAngle={2}
            cornerRadius={4}
            startAngle={90}
            endAngle={-270}
            stroke="var(--color-card)"
            strokeWidth={1}
            isAnimationActive={false}
            onClick={handleClick}
            className="cursor-pointer"
          >
            {slices.map((slice) => (
              <Cell key={slice.id} fill={slice.color} />
            ))}
          </Pie>
          <Tooltip content={<DonutTooltip />} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
