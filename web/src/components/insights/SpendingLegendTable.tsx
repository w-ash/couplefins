import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { formatCurrency } from "@/lib/format";
import { tableHeaderRowClass } from "@/lib/layout";
import type { SliceDatum } from "@/lib/spending-flow";
import { buildTransactionsUrl } from "@/lib/transaction-links";

export interface LegendBreadcrumb {
  label: string;
  onBack: () => void;
}

/**
 * The legend as a table: swatch, name, amount, share. A row that can drill
 * opens its breakdown; every other row is a link to its transactions. This
 * is also the keyboard path for what the charts do on click.
 */
export function SpendingLegendTable({
  slices,
  breadcrumb,
  canDrill,
  onDrill,
}: {
  slices: SliceDatum[];
  breadcrumb?: LegendBreadcrumb | null;
  canDrill?: (slice: SliceDatum) => boolean;
  onDrill?: (slice: SliceDatum) => void;
}) {
  const [expandedOther, setExpandedOther] = useState(false);
  const cellClass = "py-1.5 pr-3";
  return (
    <div data-testid="spending-legend">
      {breadcrumb && (
        <nav
          aria-label="Breakdown level"
          className="mb-2 flex items-center gap-1 text-xs"
        >
          <button
            type="button"
            onClick={breadcrumb.onBack}
            className="text-primary hover:underline"
          >
            All groups
          </button>
          <ChevronRight className="size-3 text-muted-foreground" />
          <span className="font-medium text-foreground">
            {breadcrumb.label}
          </span>
        </nav>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className={`${tableHeaderRowClass} text-xs`}>
            <th className={`${cellClass} font-medium`} colSpan={2}>
              Name
            </th>
            <th className={`${cellClass} text-right font-medium`}>Amount</th>
            <th className={`${cellClass} text-right font-medium`}>Share</th>
          </tr>
        </thead>
        <tbody>
          {slices.map((slice) => {
            const drillable = Boolean(canDrill?.(slice) && onDrill);
            const isOther = slice.members !== undefined;
            const label = (
              <span className="flex items-center gap-2">
                <span
                  aria-hidden
                  className="inline-block size-2.5 shrink-0 rounded-sm"
                  style={{ background: slice.color }}
                />
                <span className="truncate">{slice.name}</span>
              </span>
            );
            return (
              <tr
                key={slice.id}
                className="border-b border-border-muted transition-colors hover:bg-muted/50"
              >
                <td className={`${cellClass} w-full`} colSpan={2}>
                  {drillable ? (
                    <button
                      type="button"
                      onClick={() => onDrill?.(slice)}
                      className="flex w-full items-center justify-between gap-2 text-left text-foreground hover:text-primary"
                    >
                      {label}
                      <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
                    </button>
                  ) : isOther ? (
                    <div>
                      <button
                        type="button"
                        aria-expanded={expandedOther}
                        onClick={() => setExpandedOther((v) => !v)}
                        className="flex w-full items-center justify-between gap-2 text-left text-foreground hover:text-primary"
                      >
                        {label}
                        <ChevronRight
                          className={`size-3.5 shrink-0 text-muted-foreground transition-transform ${expandedOther ? "rotate-90" : ""}`}
                        />
                      </button>
                      {expandedOther && (
                        <p className="mt-1 pl-4.5 text-xs text-muted-foreground">
                          {slice.members?.join(", ")} ·{" "}
                          <Link
                            to={buildTransactionsUrl(slice.link)}
                            className="text-primary hover:underline"
                          >
                            View transactions
                          </Link>
                        </p>
                      )}
                    </div>
                  ) : (
                    <Link
                      to={buildTransactionsUrl(slice.link)}
                      className="flex items-center text-foreground hover:text-primary"
                    >
                      {label}
                    </Link>
                  )}
                </td>
                <td
                  className={`${cellClass} text-right tabular-nums text-foreground`}
                >
                  {formatCurrency(slice.amount)}
                </td>
                <td
                  className={`${cellClass} text-right tabular-nums text-muted-foreground`}
                >
                  {Math.round(slice.share * 100)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
