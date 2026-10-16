import { useMemo } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ShareHistoryPointResponse } from "@/api/generated/model";
import {
  ChartTooltipRow,
  ChartTooltipShell,
} from "@/components/insights/chart-tooltip";
import { formatCurrency, formatMonthYear, formatPercent } from "@/lib/format";
import { forOwner, type Owner } from "@/lib/house";
import { getPersonChartColor } from "@/types/person";

/** One served month: its label, the point itself, and each owner's percent by id. */
interface Row {
  label: string;
  point: ShareHistoryPointResponse;
  [ownerId: string]: string | number | ShareHistoryPointResponse;
}

function HistoryTooltip({
  active,
  payload,
  owners,
  getPersonIndex,
}: {
  active?: boolean;
  payload?: Array<{ payload?: unknown }>;
  owners: Owner[];
  getPersonIndex: (id: string) => number;
}) {
  const row = payload?.[0]?.payload as Row | undefined;
  if (!active || !row) return null;
  return (
    <ChartTooltipShell title={row.label}>
      {owners.map((o) => {
        const share = forOwner(row.point.owners, o.id);
        return (
          <ChartTooltipRow
            key={o.id}
            label={o.name}
            value={
              share
                ? `${formatCurrency(share.capital)} · ${formatPercent(share.percent)}`
                : "—"
            }
            swatch={getPersonChartColor(getPersonIndex(o.id))}
          />
        );
      })}
    </ChartTooltipShell>
  );
}

/** Each owner's percentage of the house, one point per served month. */
export function ShareHistoryChart({
  history,
  owners,
  getPersonIndex,
  height = 160,
}: {
  history: ShareHistoryPointResponse[];
  owners: Owner[];
  getPersonIndex: (id: string) => number;
  height?: number;
}) {
  const rows = useMemo(
    () =>
      history.map(
        (point): Row => ({
          label: formatMonthYear(point.year, point.month),
          point,
          ...Object.fromEntries(
            owners.map((o) => [
              o.id,
              forOwner(point.owners, o.id)?.percent ?? 0,
            ]),
          ),
        }),
      ),
    [history, owners],
  );
  return (
    <div>
      <div
        role="img"
        aria-label={`Share of the house over time for ${owners.map((o) => o.name).join(" and ")}`}
      >
        <ResponsiveContainer width="100%" height={height}>
          <LineChart
            data={rows}
            margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
          >
            <XAxis
              dataKey="label"
              tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis hide domain={[0, 100]} />
            <Tooltip
              content={
                <HistoryTooltip
                  owners={owners}
                  getPersonIndex={getPersonIndex}
                />
              }
            />
            {owners.map((o) => (
              <Line
                key={o.id}
                dataKey={o.id}
                stroke={getPersonChartColor(getPersonIndex(o.id))}
                strokeWidth={2}
                dot={history.length < 2}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
        {owners.map((o) => (
          <li key={o.id} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="h-0.5 w-3 rounded-full"
              style={{
                backgroundColor: getPersonChartColor(getPersonIndex(o.id)),
              }}
            />
            {o.name}
          </li>
        ))}
      </ul>
    </div>
  );
}
