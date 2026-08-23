import { ArrowRight, CheckCircle2, Clock } from "lucide-react";
import type { ReactNode } from "react";
import type {
  LedgerMonthResponse,
  LedgerSettlementResponse,
} from "@/api/generated/model";
import { Card } from "@/components/Card";
import { ExpandChevron } from "@/components/ExpandChevron";
import { PersonBadge } from "@/components/PersonBadge";
import { SectionHeader } from "@/components/SectionHeader";
import { cn } from "@/lib/cn";
import { formatCurrency, formatShortDate, MONTHS } from "@/lib/format";

export function ledgerMonthKey(m: { year: number; month: number }): string {
  return `${m.year}-${m.month}`;
}

// When the covering payments landed — the newest one wins (mirrors the
// backend's month history derivation).
function coveredDate(
  month: LedgerMonthResponse,
  settlements: LedgerSettlementResponse[],
): string | null {
  let newest: string | null = null;
  for (const id of month.covering_settlement_ids) {
    const s = settlements.find((entry) => entry.id === id);
    if (s && (newest === null || s.settled_at > newest)) {
      newest = s.settled_at;
    }
  }
  return newest;
}

function StatusChip({
  month,
  settlements,
}: {
  month: LedgerMonthResponse;
  settlements: LedgerSettlementResponse[];
}) {
  if (month.status === "settled") {
    const date = coveredDate(month, settlements);
    const label = month.is_offset
      ? "offset"
      : date
        ? `settled ${formatShortDate(date)}`
        : "settled";
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-primary-muted px-2 py-0.5 text-xs font-medium text-primary-muted-foreground">
        <CheckCircle2 className="size-3" />
        {label}
      </span>
    );
  }
  if (month.status === "partially_settled") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-warning-muted px-2 py-0.5 text-xs font-medium text-warning-muted-foreground">
        <Clock className="size-3" />
        partial — {formatCurrency(month.remaining)} left
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
      <ArrowRight className="size-3" />
      carried forward
    </span>
  );
}

export function LedgerMonthList({
  months,
  year,
  settlements,
  expandedKey,
  onToggle,
  getPersonName,
  getPersonColor,
  renderExpanded,
  emptyLabel,
}: {
  // Scoped to `year` by the caller; rendered oldest first regardless of
  // the order they arrive in.
  months: LedgerMonthResponse[];
  year: number;
  settlements: LedgerSettlementResponse[];
  expandedKey: string | null;
  onToggle: (month: LedgerMonthResponse) => void;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
  // Month-scoped drill-down content — supplied by the page, which owns the
  // month-scoped data fetch.
  renderExpanded: (month: LedgerMonthResponse) => ReactNode;
  // Shown in place of the list when the year holds no rows. Omit to render
  // nothing at all.
  emptyLabel?: string;
}) {
  if (months.length === 0 && emptyLabel === undefined) return null;

  const oldestFirst = [...months].sort((a, b) => a.month - b.month);

  return (
    <Card>
      <SectionHeader
        title="Months"
        description={`Each ${year} month's balance and how the ledger covered it`}
      />
      {months.length === 0 && (
        <p className="text-sm text-muted-foreground">{emptyLabel}</p>
      )}
      <div className="divide-y divide-border-muted">
        {oldestFirst.map((m) => {
          const key = ledgerMonthKey(m);
          const isExpanded = expandedKey === key;
          // A zero-amount gross carries an arbitrary direction — the API
          // already nulls it, so a non-null gross is always renderable.
          const gross = m.gross;
          return (
            <div key={key}>
              <button
                type="button"
                onClick={() => onToggle(m)}
                aria-expanded={isExpanded}
                className={cn(
                  "flex min-h-11 w-full flex-wrap items-center gap-x-3 gap-y-1 px-1 py-3 text-left transition-colors",
                  "hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              >
                <ExpandChevron expanded={isExpanded} />
                <span className="min-w-28 font-medium text-foreground">
                  {MONTHS[m.month - 1]} {m.year}
                </span>
                <span className="text-sm text-muted-foreground">
                  {gross ? (
                    <>
                      <PersonBadge
                        name={getPersonName(gross.from_person_id)}
                        accentColor={getPersonColor(gross.from_person_id)}
                        size="xs"
                      />{" "}
                      owes{" "}
                      <span className="tabular-nums text-foreground">
                        {formatCurrency(gross.amount)}
                      </span>{" "}
                      gross
                    </>
                  ) : (
                    "No balance"
                  )}
                </span>
                <span className="ml-auto">
                  <StatusChip month={m} settlements={settlements} />
                </span>
              </button>
              {isExpanded && (
                <div className="space-y-4 pt-1 pb-4 sm:pl-7">
                  {renderExpanded(m)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
