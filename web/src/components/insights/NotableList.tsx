import {
  ArrowDownRight,
  ArrowUpRight,
  RotateCcw,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { Link } from "react-router";
import { formatCurrency } from "@/lib/format";
import type { NotableItem, NotableKind } from "@/lib/insights-data";
import { buildTransactionsUrl } from "@/lib/transaction-links";

const KIND_STYLE: Record<
  NotableKind,
  { Icon: typeof ArrowUpRight; className: string }
> = {
  up: { Icon: ArrowUpRight, className: "text-destructive" },
  down: { Icon: ArrowDownRight, className: "text-positive" },
  new: { Icon: Sparkles, className: "text-muted-foreground" },
  streak: { Icon: TrendingUp, className: "text-warning" },
  refund: { Icon: RotateCcw, className: "text-positive" },
};

/** A short list of what moved this month, each line a link to its rows. */
export function NotableList({ items }: { items: NotableItem[] }) {
  return (
    <ul className="divide-y divide-border-muted" data-testid="notable-list">
      {items.map((item) => {
        const { Icon, className } = KIND_STYLE[item.kind];
        return (
          <li key={item.id}>
            <Link
              to={buildTransactionsUrl(item.link)}
              className="flex items-center gap-3 py-2 text-sm transition-colors hover:bg-muted/50"
            >
              <Icon className={`size-4 shrink-0 ${className}`} aria-hidden />
              <span className="flex-1 text-foreground">{item.text}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {formatCurrency(item.amount)}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
