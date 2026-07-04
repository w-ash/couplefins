import { Link2, Loader2, X } from "lucide-react";
import { useCallback, useState } from "react";
import type {
  LinkedTransactionResponse,
  MonthReference,
  SettlementResponse,
} from "@/api/generated/model";
import {
  useMarkTransactionAsSettlement,
  useUnlinkSettlementTransaction,
} from "@/api/generated/settlements/settlements";
import { Button } from "@/components/Button";
import { CandidateChecklist } from "@/components/CandidateChecklist";
import { Dialog, DialogFooter, DialogHeader } from "@/components/Dialog";
import { InlineError } from "@/components/InlineError";
import { PersonBadge } from "@/components/PersonBadge";
import { formatCurrency } from "@/lib/format";

function LinkedRow({
  tx,
  settlementId,
  getPersonName,
  getPersonColor,
  onSuccess,
}: {
  tx: LinkedTransactionResponse;
  settlementId: string;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
  onSuccess: () => void;
}) {
  const unlinkMutation = useUnlinkSettlementTransaction({
    mutation: { onSuccess },
  });

  return (
    <div className="flex items-center gap-2 rounded-md bg-muted/30 px-3 py-1.5 text-sm">
      <PersonBadge
        name={getPersonName(tx.payer_person_id)}
        accentColor={getPersonColor(tx.payer_person_id)}
        size="xs"
      />
      <span className="min-w-0 truncate text-foreground">{tx.merchant}</span>
      <span className="ml-auto shrink-0 tabular-nums text-foreground">
        {formatCurrency(tx.amount)}
      </span>
      <button
        type="button"
        onClick={() =>
          unlinkMutation.mutate({
            settlementId,
            transactionId: tx.id,
          })
        }
        disabled={unlinkMutation.isPending}
        className="shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={`Unlink ${tx.merchant}`}
      >
        {unlinkMutation.isPending ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <X className="size-3.5" />
        )}
      </button>
    </div>
  );
}

export function PosthocLinkDialog({
  open,
  onClose,
  settlement,
  persons,
  getPersonName,
  getPersonColor,
  onSuccess,
  latestTransactionMonth,
}: {
  open: boolean;
  onClose: () => void;
  settlement: SettlementResponse;
  persons: Array<{ id: string; name: string }>;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
  onSuccess: () => void;
  latestTransactionMonth: MonthReference | null;
}) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isLinking, setIsLinking] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);

  const markMutation = useMarkTransactionAsSettlement();

  const handleLink = useCallback(async () => {
    if (selectedIds.length === 0) return;
    setIsLinking(true);
    setLinkError(null);

    try {
      await Promise.all(
        selectedIds.map((txId) =>
          markMutation.mutateAsync({
            data: {
              transaction_id: txId,
              settlement_id: settlement.id,
              is_settlement: true,
            },
          }),
        ),
      );
      setSelectedIds([]);
      onSuccess();
    } catch (err) {
      setLinkError(
        err instanceof Error ? err.message : "Failed to link transactions",
      );
    } finally {
      setIsLinking(false);
    }
  }, [selectedIds, settlement.id, markMutation.mutateAsync, onSuccess]);

  const linked = settlement.linked_transactions ?? [];

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogHeader title="Link bank transactions" onClose={onClose}>
        <p className="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
          <PersonBadge
            name={getPersonName(settlement.from_person_id)}
            accentColor={getPersonColor(settlement.from_person_id)}
            size="xs"
          />
          <span>paid</span>
          <PersonBadge
            name={getPersonName(settlement.to_person_id)}
            accentColor={getPersonColor(settlement.to_person_id)}
            size="xs"
          />
          <span className="tabular-nums">
            {formatCurrency(settlement.amount)}
          </span>
        </p>
        <p className="mt-2 text-xs text-muted-foreground/70">
          Linked transactions are excluded from spending totals.
        </p>
      </DialogHeader>

      {linked.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Already linked
          </p>
          <div className="space-y-1.5">
            {linked.map((tx) => (
              <LinkedRow
                key={tx.id}
                tx={tx}
                settlementId={settlement.id}
                getPersonName={getPersonName}
                getPersonColor={getPersonColor}
                onSuccess={onSuccess}
              />
            ))}
          </div>
        </div>
      )}

      <div className="mt-4">
        <CandidateChecklist
          amount={settlement.amount.toFixed(2)}
          // Annotation is optional since v1.7.5 — fall back to the
          // recording date (ISO string slicing avoids TZ shifts).
          initialSearchMonth={{
            year: settlement.year ?? Number(settlement.settled_at.slice(0, 4)),
            month:
              settlement.month ?? Number(settlement.settled_at.slice(5, 7)),
          }}
          searchFloor={null}
          persons={persons}
          selectedIds={selectedIds}
          onSelectionChange={(ids) => setSelectedIds(ids)}
          latestTransactionMonth={latestTransactionMonth}
        />
      </div>

      {linkError && (
        <div className="mt-3">
          <InlineError>{linkError}</InlineError>
        </div>
      )}

      <DialogFooter>
        <Button variant="secondary" size="sm" onClick={onClose}>
          Close
        </Button>
        {selectedIds.length > 0 && (
          <Button
            size="sm"
            onClick={handleLink}
            loading={isLinking}
            loadingText="Linking..."
            icon={<Link2 className="size-4" />}
          >
            Link {selectedIds.length}{" "}
            {selectedIds.length === 1 ? "transaction" : "transactions"}
          </Button>
        )}
      </DialogFooter>
    </Dialog>
  );
}
