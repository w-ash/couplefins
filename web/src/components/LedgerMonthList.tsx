import { ArrowRight, CheckCircle2, Clock } from "lucide-react";
import { type ReactNode, useMemo } from "react";
import type {
  LedgerMonthResponse,
  LedgerSettlementResponse,
  MonthSettlementStatus,
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

const STATUS_CHIP: Record<
  MonthSettlementStatus,
  { icon: typeof CheckCircle2; className: string; label: string }
> = {
  settled: {
    icon: CheckCircle2,
    className: "bg-primary-muted text-primary-muted-foreground",
    label: "settled",
  },
  partially_settled: {
    icon: Clock,
    className: "bg-warning-muted text-warning-muted-foreground",
    label: "partially settled",
  },
  carried_forward: {
    icon: ArrowRight,
    className: "bg-muted text-muted-foreground",
    label: "carried forward",
  },
};

function StatusChip({
  status,
  settledDate,
}: {
  status: MonthSettlementStatus;
  // When the covering payments landed — suffixed onto a settled chip only.
  settledDate: string | null;
}) {
  const { icon: Icon, className, label } = STATUS_CHIP[status];
  const text =
    status === "settled" && settledDate
      ? `settled ${formatShortDate(settledDate)}`
      : label;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        className,
      )}
    >
      <Icon className="size-3" />
      {text}
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
  // Newest covering payment per month, keyed by ledgerMonthKey — built once,
  // since settlement history grows without bound.
  const coveredDates = useMemo(() => {
    const newest = new Map<string, string>();
    for (const s of settlements) {
      for (const p of s.portions ?? []) {
        const key = ledgerMonthKey(p);
        const prev = newest.get(key);
        if (prev === undefined || s.settled_at > prev) {
          newest.set(key, s.settled_at);
        }
      }
    }
    return newest;
  }, [settlements]);

  if (months.length === 0 && emptyLabel === undefined) return null;

  const oldestFirst = [...months].sort((a, b) => a.month - b.month);

  return (
    <Card>
      <SectionHeader
        title="Months"
        description={`Each ${year} month's balance after its payments`}
      />
      {months.length === 0 && (
        <p className="text-sm text-muted-foreground">{emptyLabel}</p>
      )}
      <div className="divide-y divide-border-muted">
        {oldestFirst.map((m) => {
          const key = ledgerMonthKey(m);
          const isExpanded = expandedKey === key;
          const balance = m.balance;
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
                  {balance ? (
                    <>
                      {/* The hero already names the year's direction — a row
                          names its person only when it runs the other way. */}
                      {m.runs_against_year && (
                        <>
                          <PersonBadge
                            name={getPersonName(balance.from_person_id)}
                            accentColor={getPersonColor(balance.from_person_id)}
                            size="xs"
                          />{" "}
                          owes{" "}
                        </>
                      )}
                      <span className="tabular-nums text-foreground">
                        {formatCurrency(balance.amount)}
                      </span>
                    </>
                  ) : (
                    "No balance"
                  )}
                </span>
                <span className="ml-auto">
                  <StatusChip
                    status={m.status}
                    settledDate={coveredDates.get(key) ?? null}
                  />
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
