import { useState } from "react";
import { errorMessage } from "@/api/client";
import {
  useFindObligationPaymentCandidates,
  useMarkObligationPaid,
} from "@/api/generated/house/house";
import type { ObligationResponse } from "@/api/generated/model";
import { Button } from "@/components/Button";
import { Dialog, DialogFooter, DialogHeader } from "@/components/Dialog";
import { InlineError } from "@/components/InlineError";
import { useInvalidateHouse } from "@/hooks/useInvalidateHouse";
import { formatCurrency, formatDate } from "@/lib/format";

function MarkPaidForm({
  obligation,
  onClose,
}: {
  obligation: ObligationResponse;
  onClose: () => void;
}) {
  const invalidate = useInvalidateHouse();
  const [picked, setPicked] = useState<string | null>(null);
  const {
    data: res,
    isLoading,
    isError,
    error,
  } = useFindObligationPaymentCandidates(obligation.id);
  const candidates = res?.status === 200 ? res.data : [];
  const mutation = useMarkObligationPaid({
    mutation: {
      onSuccess: () => {
        invalidate();
        onClose();
      },
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (picked === null || mutation.isPending) return;
        mutation.mutate({
          obligationId: obligation.id,
          data: { transaction_id: picked },
        });
      }}
      className="flex max-h-[calc(90dvh-3rem)] flex-col"
    >
      <DialogHeader
        title="Mark paid"
        subtitle={`Pick the row that paid ${obligation.name}, due ${formatDate(obligation.due)}.`}
        onClose={onClose}
      />
      <div className="mt-4 min-h-0 flex-1 overflow-y-auto p-1">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Finding rows...</p>
        ) : isError || (res && res.status !== 200) ? (
          <InlineError>
            {errorMessage(error, "Failed to find matching rows")}
          </InlineError>
        ) : candidates.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No matching rows found. Check that the payment was uploaded.
          </p>
        ) : (
          <fieldset className="space-y-2">
            <legend className="sr-only">Matching rows</legend>
            {candidates.map((c) => (
              <label
                key={c.id}
                className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border border-border p-3 text-sm has-[:checked]:border-ring has-[:checked]:bg-muted"
              >
                <input
                  type="radio"
                  name="candidate"
                  value={c.id}
                  checked={picked === c.id}
                  onChange={() => setPicked(c.id)}
                  className="mt-1 size-4"
                />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap justify-between gap-x-3">
                    <span className="font-medium">{c.merchant}</span>
                    <span className="tabular-nums">
                      {formatCurrency(Math.abs(c.amount))}
                    </span>
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {formatDate(c.date)} · {c.account_name}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
        )}
      </div>
      {mutation.isError && (
        <div className="mt-3">
          <InlineError>
            {errorMessage(mutation.error, "Failed to mark paid")}
          </InlineError>
        </div>
      )}
      <DialogFooter>
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={picked === null}
          loading={mutation.isPending}
        >
          Mark paid
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Dialog that links the row that paid an obligation. */
export function MarkPaidDialog({
  obligation,
  onClose,
}: {
  obligation: ObligationResponse | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={obligation !== null} onClose={onClose}>
      {obligation && <MarkPaidForm obligation={obligation} onClose={onClose} />}
    </Dialog>
  );
}
