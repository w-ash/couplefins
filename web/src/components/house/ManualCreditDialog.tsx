import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errorMessage } from "@/api/client";
import { useRecordManualEntry } from "@/api/generated/house/house";
import type { ContributionKind } from "@/api/generated/model";
import { Button } from "@/components/Button";
import { Dialog, DialogFooter, DialogHeader } from "@/components/Dialog";
import { InlineError } from "@/components/InlineError";
import {
  OwnerSharesEditor,
  useOwnerShares,
} from "@/components/OwnerSharesEditor";
import { HOUSE_QUERY_KEYS } from "@/hooks/useRealtimeSync";
import { cn } from "@/lib/cn";
import { localISODate } from "@/lib/format";
import {
  CONTRIBUTION_KIND_LABELS,
  DEFAULT_MANUAL_ACCOUNT,
  type Owner,
} from "@/lib/house";
import {
  baseInputClass,
  fieldLabelClass,
  selectInputClass,
} from "@/lib/input-styles";

const KINDS = Object.keys(CONTRIBUTION_KIND_LABELS) as ContributionKind[];

function CreditForm({
  owners,
  onClose,
}: {
  owners: Owner[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [accountName, setAccountName] = useState(DEFAULT_MANUAL_ACCOUNT);
  const [date, setDate] = useState(localISODate());
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<ContributionKind>("closing");
  const [description, setDescription] = useState("");
  const [documentRef, setDocumentRef] = useState("");
  const shares = useOwnerShares(owners, 50);

  const mutation = useRecordManualEntry({
    mutation: {
      onSuccess: () => {
        for (const queryKey of HOUSE_QUERY_KEYS) {
          queryClient.invalidateQueries({ queryKey });
        }
        onClose();
      },
    },
  });

  const amountValue = Number(amount);
  const canSubmit =
    amount.trim() !== "" &&
    amountValue > 0 &&
    date !== "" &&
    description.trim() !== "" &&
    accountName.trim() !== "" &&
    shares.payload != null &&
    !shares.invalid;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || !shares.payload) return;
    mutation.mutate({
      data: {
        account_name: accountName.trim(),
        date,
        amount: amountValue,
        description: description.trim(),
        document_ref: documentRef.trim(),
        share_kind: kind,
        owner_shares: shares.payload,
      },
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex max-h-[calc(90dvh-3rem)] flex-col"
    >
      <DialogHeader
        title="Record a credit"
        subtitle="A contribution that passed through no imported account."
        onClose={onClose}
      />
      <div className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto p-1">
        <label className={fieldLabelClass}>
          Account name
          <input
            value={accountName}
            onChange={(e) => setAccountName(e.target.value)}
            className={cn("w-full", baseInputClass)}
          />
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className={fieldLabelClass}>
            Date
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
          <label className={fieldLabelClass}>
            Amount
            <input
              type="number"
              min={0}
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
        </div>
        <label className={fieldLabelClass}>
          Kind
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as ContributionKind)}
            className={cn("w-full", selectInputClass)}
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {CONTRIBUTION_KIND_LABELS[k]}
              </option>
            ))}
          </select>
        </label>
        <label className={fieldLabelClass}>
          Description
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className={cn("w-full", baseInputClass)}
          />
        </label>
        <label className={fieldLabelClass}>
          Document reference
          <input
            value={documentRef}
            onChange={(e) => setDocumentRef(e.target.value)}
            className={cn("w-full", baseInputClass)}
          />
        </label>
        {shares.pair && (
          <OwnerSharesEditor
            owners={shares.pair}
            values={shares.values}
            absAmount={amountValue > 0 ? amountValue : undefined}
            isDefault={shares.values[0] === "50" && shares.values[1] === "50"}
            onChange={shares.onChange}
            onReset={shares.onReset}
          />
        )}
      </div>
      {mutation.isError && (
        <div className="mt-3">
          <InlineError>
            {errorMessage(mutation.error, "Failed to record the credit")}
          </InlineError>
        </div>
      )}
      <DialogFooter>
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={!canSubmit}
          loading={mutation.isPending}
        >
          Record a credit
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Dialog to record a contribution that passed through no imported account. */
export function ManualCreditDialog({
  open,
  owners,
  onClose,
}: {
  open: boolean;
  owners: Owner[];
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onClose={onClose}>
      {open && <CreditForm owners={owners} onClose={onClose} />}
    </Dialog>
  );
}
