import { Link } from "react-router";
import { formatCurrency } from "@/lib/format";
import type { SliceDatum } from "@/lib/spending-flow";
import { buildTransactionsUrl } from "@/lib/transaction-links";

/** Proportional horizontal bars, biggest first — the most readable form for
 * a dozen rows. Each row links to its transactions; a drillable row drills. */
export function SpendingBars({
  slices,
  canDrill,
  onDrill,
}: {
  slices: SliceDatum[];
  canDrill?: (slice: SliceDatum) => boolean;
  onDrill?: (slice: SliceDatum) => void;
}) {
  const max = slices[0]?.amount ?? 0;
  return (
    <ul className="space-y-2" data-testid="spending-bars">
      {slices.map((slice) => {
        const width = max > 0 ? `${(slice.amount / max) * 100}%` : "0%";
        const body = (
          <>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate text-foreground">{slice.name}</span>
              <span className="shrink-0 tabular-nums text-foreground">
                {formatCurrency(slice.amount)}
                <span className="ml-1.5 text-xs text-muted-foreground">
                  {Math.round(slice.share * 100)}%
                </span>
              </span>
            </div>
            <div className="mt-1 h-2 rounded-full bg-muted">
              <div
                className="h-2 rounded-full transition-[width] duration-300 ease-out"
                style={{ width, background: slice.color }}
              />
            </div>
          </>
        );
        const className =
          "block rounded-md px-1.5 py-1 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
        return (
          <li key={slice.id}>
            {canDrill?.(slice) && onDrill ? (
              <button
                type="button"
                className={`w-full text-left ${className}`}
                onClick={() => onDrill(slice)}
              >
                {body}
              </button>
            ) : (
              <Link to={buildTransactionsUrl(slice.link)} className={className}>
                {body}
              </Link>
            )}
          </li>
        );
      })}
    </ul>
  );
}
