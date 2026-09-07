import { useCallback } from "react";
import { useNavigate } from "react-router";
import {
  Layer,
  ResponsiveContainer,
  Sankey,
  type SankeyLinkProps,
  type SankeyNode,
  type SankeyNodeProps,
  Tooltip,
  useChartWidth,
} from "recharts";
import { formatCurrency } from "@/lib/format";
import type { FlowNodeDatum, SankeyDataset } from "@/lib/spending-flow";
import { buildTransactionsUrl } from "@/lib/transaction-links";
import { ChartTooltipRow, ChartTooltipShell } from "./chart-tooltip";

type FlowNode = SankeyNode & FlowNodeDatum;

const NODE_WIDTH = 12;
const LABEL_GAP = 8;
// Nodes are at least NODE_PADDING apart, so a one-line 10px label fits
// beside even a sliver; the amount line needs a taller bar.
const MIN_LABEL_HEIGHT = 3;
const TWO_LINE_HEIGHT = 26;
const NODE_PADDING = 10;
const LABEL_WIDTH = 150;

function pct(amount: number, total: number): string {
  return total > 0 ? `${Math.round((amount / total) * 100)}%` : "";
}

function FlowNodeShape({
  x,
  y,
  width,
  height,
  payload,
  total,
}: SankeyNodeProps & { total: number }) {
  const chartWidth = useChartWidth() ?? 0;
  const node = payload as FlowNode;
  // Right-hand column labels sit to the left of the bar so they stay inside
  // the chart; every other column labels to the right.
  const isLast = x + width + LABEL_GAP + LABEL_WIDTH > chartWidth;
  const labelX = isLast ? x - LABEL_GAP : x + width + LABEL_GAP;
  const showLabel = height >= MIN_LABEL_HEIGHT;
  return (
    <Layer className="cursor-pointer">
      <title>{`${node.name}: ${formatCurrency(node.amount)}`}</title>
      <rect
        x={x}
        y={y}
        width={width}
        height={Math.max(height, 1)}
        rx={2}
        fill={node.color}
      />
      {showLabel && (
        <text
          x={labelX}
          y={y + height / 2}
          textAnchor={isLast ? "end" : "start"}
          fill="var(--color-foreground)"
          fontSize={height >= TWO_LINE_HEIGHT ? 11 : 10}
        >
          <tspan dy={height >= TWO_LINE_HEIGHT ? -3 : 3.5}>{node.name}</tspan>
          {height >= TWO_LINE_HEIGHT && (
            <tspan
              x={labelX}
              dy={13}
              fill="var(--color-muted-foreground)"
              className="tabular-nums"
            >
              {formatCurrency(node.amount)} · {pct(node.amount, total)}
            </tspan>
          )}
        </text>
      )}
    </Layer>
  );
}

function FlowLinkShape({
  sourceX,
  targetX,
  sourceY,
  targetY,
  sourceControlX,
  targetControlX,
  linkWidth,
  index,
  payload,
}: SankeyLinkProps) {
  const source = payload.source as FlowNode;
  const target = payload.target as FlowNode;
  const id = `flow-link-${index}`;
  return (
    <Layer>
      <defs>
        <linearGradient
          id={id}
          gradientUnits="userSpaceOnUse"
          x1={sourceX}
          x2={targetX}
        >
          <stop offset="0%" stopColor={source.color} />
          <stop offset="100%" stopColor={target.color} />
        </linearGradient>
      </defs>
      <path
        d={`M${sourceX},${sourceY} C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY}`}
        fill="none"
        stroke={`url(#${id})`}
        strokeWidth={Math.max(linkWidth, 1)}
        strokeOpacity={0.3}
      />
    </Layer>
  );
}

/** What the tooltip reads: the domain datum, without the layout geometry
 * the node and link shapes draw with. Recharts resolves a link's source and
 * target indices to the node objects before it hands them over. */
type TooltipDatum =
  | FlowNodeDatum
  | { source: FlowNodeDatum; target: FlowNodeDatum; value: number };

export function FlowTooltip({
  active,
  payload,
  total,
}: {
  active?: boolean;
  // Recharts wraps the Sankey datum one level deeper than its other charts:
  // the tooltip entry's payload is `{ payload, name, value }`, for a node and
  // a link alike.
  payload?: Array<{ payload?: { payload?: TooltipDatum } }>;
  total: number;
}) {
  const item = payload?.[0]?.payload?.payload;
  if (!active || !item) return null;
  if ("source" in item) {
    return (
      <ChartTooltipShell>
        <ChartTooltipRow
          label={`${item.source.name} → ${item.target.name}`}
          value={formatCurrency(item.value)}
        />
      </ChartTooltipShell>
    );
  }
  return (
    <ChartTooltipShell>
      <ChartTooltipRow
        label={item.name}
        value={formatCurrency(item.amount)}
        swatch={item.color}
      />
      <p className="mt-0.5 text-muted-foreground">
        {pct(item.amount, total)} of the period · {item.transactionCount}{" "}
        transactions
        {item.members ? ` · ${item.members.join(", ")}` : ""}
      </p>
      <p className="mt-0.5 text-primary">Click to view transactions</p>
    </ChartTooltipShell>
  );
}

const ROW_HEIGHT = 28;
const MIN_HEIGHT = 360;
const MAX_HEIGHT = 760;

/** Enough height for the busiest column to label every node. */
function flowChartHeight(dataset: SankeyDataset): number {
  const counts = { source: 0, group: 0, category: 0 };
  for (const n of dataset.nodes)
    counts[n.kind === "other" ? "category" : n.kind]++;
  const busiest = Math.max(counts.source, counts.group, counts.category);
  return Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, busiest * ROW_HEIGHT + 60));
}

export function SpendingFlowChart({ dataset }: { dataset: SankeyDataset }) {
  const navigate = useNavigate();
  const chartHeight = flowChartHeight(dataset);
  const total = dataset.nodes
    .filter((n) => n.kind === "source")
    .reduce((s, n) => s + n.amount, 0);

  const handleClick = useCallback(
    (item: SankeyNodeProps | SankeyLinkProps, type: "node" | "link") => {
      const node =
        type === "node"
          ? (item.payload as FlowNode)
          : ((item as SankeyLinkProps).payload.target as FlowNode);
      navigate(buildTransactionsUrl(node.link));
    },
    [navigate],
  );

  const renderNode = useCallback(
    (props: SankeyNodeProps) => <FlowNodeShape {...props} total={total} />,
    [total],
  );

  return (
    <div
      className="overflow-x-auto"
      data-testid="spending-flow-chart"
      role="img"
      aria-label="Spending flow from who paid, through category groups, to categories"
    >
      <div className="min-w-[640px]">
        <ResponsiveContainer width="100%" height={chartHeight}>
          <Sankey
            data={dataset}
            nodeWidth={NODE_WIDTH}
            nodePadding={NODE_PADDING}
            iterations={64}
            sort={false}
            margin={{ top: 8, right: 8, bottom: 8, left: 8 }}
            node={renderNode}
            link={FlowLinkShape}
            onClick={handleClick}
            title="Spending flow"
            desc="Where the period's money came from and which categories it went to"
          >
            <Tooltip content={<FlowTooltip total={total} />} />
          </Sankey>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
