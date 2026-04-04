import { Link2, Loader2, X } from "lucide-react";
import { useCallback, useState } from "react";
import type {
  LinkedTransactionResponse,
  SettlementResponse,
} from "@/api/generated/model";
import {
  useMarkTransactionAsSettlement,
  useUnlinkSettlementTransaction,
} from "@/api/generated/settlements/settlements";
import { Button } from "@/components/Button";
import { CandidateChecklist } from "@/components/CandidateChecklist";
import { InlineError } from "@/components/InlineError";
import { PersonBadge } from "@/components/PersonBadge";
import { useDialogSync } from "@/hooks/useDialogSync";
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
}: {
  open: boolean;
  onClose: () => void;
  settlement: SettlementResponse;
  persons: Array<{ id: string; name: string }>;
  getPersonName: (id: string) => string;
  getPersonColor: (id: string) => string;
  onSuccess: () => void;
}) {
  const dialogRef = useDialogSync(open);
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
    <dialog
      ref={dialogRef}
      onClose={onClose}
      className="mx-4 w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-lg backdrop:bg-black/40"
    >
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-medium text-foreground">
            Link bank transactions
          </h2>
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
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="rounded-md p-1 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="size-4" />
        </button>
      </div>

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
          month={settlement.month}
          year={settlement.year}
          persons={persons}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
        />
      </div>

      {linkError && (
        <div className="mt-3">
          <InlineError>{linkError}</InlineError>
        </div>
      )}

      <div className="mt-5 flex items-center justify-end gap-3">
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
      </div>
    </dialog>
  );
}
