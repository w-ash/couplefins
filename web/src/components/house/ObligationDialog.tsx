import { useState } from "react";
import { errorMessage } from "@/api/client";
import {
  useCreateObligation,
  useUpdateObligation,
} from "@/api/generated/house/house";
import type {
  LoanResponse,
  ObligationKind,
  ObligationRecordResponse,
  ObligationResponse,
} from "@/api/generated/model";
import { Button } from "@/components/Button";
import { Dialog, DialogFooter, DialogHeader } from "@/components/Dialog";
import { InlineError } from "@/components/InlineError";
import { useInvalidateHouse } from "@/hooks/useInvalidateHouse";
import { cn } from "@/lib/cn";
import { OBLIGATION_KIND_LABELS } from "@/lib/house";
import {
  baseInputClass,
  fieldLabelClass,
  selectInputClass,
} from "@/lib/input-styles";

const KINDS = Object.keys(OBLIGATION_KIND_LABELS) as ObligationKind[];

/** An obligation being edited; the record adds the fields figures omit. */
export interface EditingObligation {
  obligation: ObligationResponse;
  record: ObligationRecordResponse | undefined;
}

type LoanChoice = Pick<LoanResponse, "id" | "name">;

function ObligationForm({
  editing,
  loans,
  pastLoans,
  onClose,
}: {
  editing: EditingObligation | null;
  loans: LoanChoice[];
  pastLoans: LoanChoice[];
  onClose: () => void;
}) {
  const invalidate = useInvalidateHouse();
  const ob = editing?.obligation;
  const [kind, setKind] = useState<ObligationKind>(ob?.kind ?? "property_tax");
  const [description, setDescription] = useState(ob?.name ?? "");
  const [amount, setAmount] = useState(ob ? String(ob.amount) : "");
  const [isEstimate, setIsEstimate] = useState(ob?.is_estimate ?? false);
  const [dueOn, setDueOn] = useState(ob?.due ?? "");
  const [lateAfter, setLateAfter] = useState(ob?.late_after ?? "");
  const [paysFrom, setPaysFrom] = useState(ob?.pays_from ?? "");
  const [loanId, setLoanId] = useState(ob?.loan_id ?? "");
  const [notes, setNotes] = useState(editing?.record?.notes ?? "");

  const onSuccess = () => {
    invalidate();
    onClose();
  };
  const create = useCreateObligation({ mutation: { onSuccess } });
  const update = useUpdateObligation({ mutation: { onSuccess } });
  const mutation = editing ? update : create;

  const canSubmit =
    description.trim() !== "" &&
    amount.trim() !== "" &&
    Number(amount) > 0 &&
    dueOn !== "" &&
    (kind !== "loan_payment" || loanId !== "");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || mutation.isPending) return;
    const data = {
      kind,
      description: description.trim(),
      amount: Number(amount),
      is_estimate: isEstimate,
      due_on: dueOn,
      late_after: lateAfter === "" ? null : lateAfter,
      pays_from: paysFrom.trim() === "" ? null : paysFrom.trim(),
      loan_id: kind === "loan_payment" && loanId !== "" ? loanId : null,
      notes: notes.trim(),
    };
    if (editing) {
      update.mutate({ obligationId: editing.obligation.id, data });
    } else {
      create.mutate({ data });
    }
  }

  const selectableLoans = editing ? [...loans, ...pastLoans] : loans;
  const title = editing ? "Edit obligation" : "Record an obligation";
  return (
    <form
      onSubmit={handleSubmit}
      className="flex max-h-[calc(90dvh-3rem)] flex-col"
    >
      <DialogHeader
        title={title}
        subtitle="Something that comes due, and the pot that pays it."
        onClose={onClose}
      />
      <div className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto p-1">
        <label className={fieldLabelClass}>
          Kind
          <select
            value={kind}
            onChange={(e) => {
              const next = e.target.value as ObligationKind;
              setKind(next);
              if (next !== "loan_payment") setLoanId("");
            }}
            className={cn("w-full", selectInputClass)}
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {OBLIGATION_KIND_LABELS[k]}
              </option>
            ))}
          </select>
        </label>
        {kind === "loan_payment" && (
          <label className={fieldLabelClass}>
            Loan
            <select
              value={loanId}
              onChange={(e) => setLoanId(e.target.value)}
              className={cn("w-full", selectInputClass)}
            >
              <option value="">Choose a loan</option>
              {selectableLoans.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className={fieldLabelClass}>
          Description
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className={cn("w-full", baseInputClass)}
          />
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className={fieldLabelClass}>
            Amount
            <input
              type="number"
              min={0.01}
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
          <label className="flex min-h-11 items-center gap-2 self-end text-sm font-medium text-foreground">
            <input
              type="checkbox"
              checked={isEstimate}
              onChange={(e) => setIsEstimate(e.target.checked)}
              className="size-4"
            />
            Estimate
          </label>
          <label className={fieldLabelClass}>
            Due
            <input
              type="date"
              value={dueOn}
              onChange={(e) => setDueOn(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
          <label className={fieldLabelClass}>
            Late after (optional)
            <input
              type="date"
              value={lateAfter}
              onChange={(e) => setLateAfter(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
        </div>
        <label className={fieldLabelClass}>
          Pays from (pot name, optional)
          <input
            value={paysFrom}
            onChange={(e) => setPaysFrom(e.target.value)}
            className={cn("w-full", baseInputClass)}
          />
        </label>
        <label className={fieldLabelClass}>
          Notes
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className={cn("w-full", baseInputClass)}
          />
        </label>
      </div>
      {mutation.isError && (
        <div className="mt-3">
          <InlineError>
            {errorMessage(mutation.error, "Failed to save the obligation")}
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
          {editing ? "Save obligation" : "Record an obligation"}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Dialog to record an obligation, or edit one. */
export function ObligationDialog({
  open,
  editing = null,
  loans,
  pastLoans = [],
  onClose,
}: {
  open: boolean;
  editing?: EditingObligation | null;
  loans: LoanChoice[];
  pastLoans?: LoanChoice[];
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onClose={onClose}>
      {open && (
        <ObligationForm
          editing={editing}
          loans={loans}
          pastLoans={pastLoans}
          onClose={onClose}
        />
      )}
    </Dialog>
  );
}
