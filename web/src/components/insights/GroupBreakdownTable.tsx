import { ArrowRight, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { ExpandChevron } from "@/components/ExpandChevron";
import { getCategoryGroupIcon } from "@/lib/category-icons";
import { formatCurrency, getDeltaColorClass } from "@/lib/format";
import type { GroupRow } from "@/lib/insights-data";
import { tableHeaderRowClass } from "@/lib/layout";
import { buildTransactionsUrl } from "@/lib/transaction-links";
import { MiniTrendLine } from "./MiniTrendLine";

function DeltaChip({ delta }: { delta: GroupRow["delta"] }) {
  if (!delta) return <span className="text-muted-foreground">—</span>;
  if (delta.isNew)
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Sparkles className="size-3" aria-hidden />
        New
      </span>
    );
  const rounded = Math.round(delta.pct);
  return (
    <span
      className={`text-xs tabular-nums ${getDeltaColorClass(delta.pct)}`}
      title={delta.label}
    >
      {rounded > 0 ? "+" : ""}
      {rounded}%
      <span className="ml-1 hidden text-muted-foreground lg:inline">
        {delta.label}
      </span>
    </span>
  );
}

/**
 * One row per category group: trend, period amount, share, delta, count.
 * A row expands to its categories; the group and every category link to
 * the Transactions list that sums to the figure shown.
 */
export function GroupBreakdownTable({
  rows,
  iconMap,
  selectedMonth,
}: {
  rows: GroupRow[];
  iconMap: Map<string, string | null>;
  selectedMonth: number;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const cellClass = "py-2 pr-3";
  return (
    <div className="overflow-x-auto" data-testid="group-breakdown">
      <table className="w-full min-w-[560px] text-sm">
        <thead>
          <tr className={`${tableHeaderRowClass} text-xs`}>
            <th className={`${cellClass} font-medium`}>Group</th>
            <th className={`${cellClass} w-28 font-medium`}>Trend</th>
            <th className={`${cellClass} text-right font-medium`}>Amount</th>
            <th className={`${cellClass} text-right font-medium`}>Share</th>
            <th className={`${cellClass} text-right font-medium`}>Change</th>
            <th
              className={`${cellClass} hidden text-right font-medium sm:table-cell`}
            >
              Txns
            </th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const Icon = getCategoryGroupIcon(iconMap.get(row.key) ?? null);
            const isOpen = expanded === row.key;
            return [
              <tr
                key={row.key}
                className="border-b border-border-muted transition-colors hover:bg-muted/50"
              >
                <td className={cellClass}>
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    onClick={() => setExpanded(isOpen ? null : row.key)}
                    className="flex items-center gap-2 text-left font-medium text-foreground"
                  >
                    <ExpandChevron expanded={isOpen} />
                    <span
                      aria-hidden
                      className="inline-block size-2.5 shrink-0 rounded-sm"
                      style={{ background: row.color }}
                    />
                    <Icon
                      className="size-4 text-muted-foreground"
                      aria-hidden
                    />
                    {row.name}
                  </button>
                </td>
                <td className={`${cellClass} w-28`}>
                  <MiniTrendLine
                    trend={row.trend}
                    priorTrend={row.priorTrend}
                    color={row.color}
                    selectedMonth={selectedMonth}
                  />
                </td>
                <td
                  className={`${cellClass} text-right tabular-nums text-foreground`}
                >
                  {formatCurrency(row.amount)}
                </td>
                <td
                  className={`${cellClass} text-right tabular-nums text-muted-foreground`}
                >
                  {Math.round(row.share * 100)}%
                </td>
                <td className={`${cellClass} text-right`}>
                  <DeltaChip delta={row.delta} />
                </td>
                <td
                  className={`${cellClass} hidden text-right tabular-nums text-muted-foreground sm:table-cell`}
                >
                  {row.transactionCount}
                </td>
                <td className="py-2 text-right">
                  <Link
                    to={buildTransactionsUrl(row.link)}
                    className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    aria-label={`View ${row.name} transactions`}
                  >
                    View <ArrowRight className="size-3" aria-hidden />
                  </Link>
                </td>
              </tr>,
              isOpen && (
                <tr key={`${row.key}-categories`} className="bg-muted/30">
                  <td colSpan={7} className="px-3 py-2">
                    <ul className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
                      {row.categories.map((cat) => (
                        <li key={cat.name}>
                          <Link
                            to={buildTransactionsUrl(cat.link)}
                            className="flex items-baseline justify-between gap-3 rounded px-1 py-0.5 text-sm hover:bg-muted/60"
                          >
                            <span className="truncate text-muted-foreground">
                              {cat.name}
                            </span>
                            <span className="shrink-0 tabular-nums text-foreground">
                              {formatCurrency(cat.amount)}
                              <span className="ml-1.5 text-xs text-muted-foreground">
                                {cat.transactionCount}
                              </span>
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </td>
                </tr>
              ),
            ];
          })}
        </tbody>
      </table>
    </div>
  );
}
