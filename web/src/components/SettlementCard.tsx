import { CheckCircle2 } from "lucide-react";
import { formatCurrency } from "@/lib/format";
import type { Settlement } from "@/lib/reconciliation";
import { getPersonAccentColor } from "@/types/person";

export function SettlementCard({
  settlement,
  personNames,
  personIndexMap,
  periodLabel,
}: {
  settlement: Settlement;
  personNames: Map<string, string>;
  personIndexMap: Map<string, number>;
  periodLabel?: string;
}) {
  const isSettled = settlement.amount === 0;
  const fromName = personNames.get(settlement.from_person_id) ?? "Unknown";
  const toName = personNames.get(settlement.to_person_id) ?? "Unknown";
  const fromColor = getPersonAccentColor(
    personIndexMap.get(settlement.from_person_id) ?? -1,
  );

  return (
    <div className="rounded-xl border border-primary/20 bg-card p-8 shadow-md">
      {periodLabel && (
        <p className="mb-1 text-center text-sm font-medium text-muted-foreground">
          {periodLabel}
        </p>
      )}
      <p className="text-center text-2xl font-semibold text-foreground">
        {isSettled ? (
          <span className="inline-flex items-center gap-2 text-primary">
            <CheckCircle2 className="size-6" />
            All settled!
          </span>
        ) : (
          <>
            <span
              className={`inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-lg font-semibold ${fromColor}`}
            >
              {fromName}
            </span>{" "}
            owes {toName}{" "}
            <span className="tabular-nums">
              {formatCurrency(settlement.amount)}
            </span>
          </>
        )}
      </p>
    </div>
  );
}
