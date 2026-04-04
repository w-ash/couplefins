import type { LinkedTransactionResponse } from "@/api/generated/model";
import { PersonBadge } from "@/components/PersonBadge";
import { formatCurrency, formatDate } from "@/lib/format";

export function LinkedTransactionSubrows({
  linkedTransactions,
  getPersonName,
  getPersonColor,
}: {
  linkedTransactions: LinkedTransactionResponse[];
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
}) {
  if (linkedTransactions.length === 0) return null;

  return (
    <div className="border-l-2 border-primary/30 ml-4 pl-3 py-1.5 space-y-1.5">
      {linkedTransactions.map((tx) => (
        <div
          key={tx.id}
          className="flex items-center gap-3 bg-muted/30 rounded-md px-3 py-1.5 text-sm"
        >
          <PersonBadge
            name={getPersonName(tx.payer_person_id)}
            accentColor={getPersonColor(tx.payer_person_id)}
            size="xs"
          />
          <span className="text-xs text-muted-foreground">
            {formatDate(tx.date)}
          </span>
          <span className="min-w-0 truncate text-foreground">
            {tx.merchant}
          </span>
          <span className="ml-auto shrink-0 tabular-nums text-foreground">
            {formatCurrency(tx.amount)}
          </span>
        </div>
      ))}
    </div>
  );
}
