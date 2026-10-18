import { useState } from "react";
import { errorMessage } from "@/api/client";
import { useCreateLoan, useReplaceLoan } from "@/api/generated/house/house";
import type {
  LoanKind,
  LoanRecordResponse,
  LoanResponse,
} from "@/api/generated/model";
import { Button } from "@/components/Button";
import { Dialog, DialogFooter, DialogHeader } from "@/components/Dialog";
import { InlineError } from "@/components/InlineError";
import { useInvalidateHouse } from "@/hooks/useInvalidateHouse";
import { cn } from "@/lib/cn";
import { localISODate } from "@/lib/format";
import { LOAN_KIND_LABELS } from "@/lib/house";
import {
  baseInputClass,
  fieldLabelClass,
  selectInputClass,
} from "@/lib/input-styles";

const KINDS = Object.keys(LOAN_KIND_LABELS) as LoanKind[];

/** The loan being refinanced; its terms pre-fill the replacement. */
export interface ReplacingLoan {
  loan: LoanResponse;
  record: LoanRecordResponse | undefined;
}

function LoanForm({
  replacing,
  onClose,
}: {
  replacing: ReplacingLoan | null;
  onClose: () => void;
}) {
  const invalidate = useInvalidateHouse();
  const today = localISODate();
  const loan = replacing?.loan;
  const record = replacing?.record;

  const [name, setName] = useState("");
  const [lender, setLender] = useState(loan?.lender ?? "");
  const [kind, setKind] = useState<LoanKind>(loan?.kind ?? "amortizing");
  const [principal, setPrincipal] = useState(loan ? String(loan.balance) : "");
  const [rate, setRate] = useState(loan ? String(loan.rate_percent) : "");
  const [payment, setPayment] = useState(loan ? String(loan.payment) : "");
  const [term, setTerm] = useState(
    record?.term_months != null ? String(record.term_months) : "",
  );
  const [firstDue, setFirstDue] = useState(loan?.next_due ?? "");
  const [statementBalance, setStatementBalance] = useState(
    loan ? String(loan.balance) : "",
  );
  const [statementDate, setStatementDate] = useState(loan ? today : "");
  const [notes, setNotes] = useState(record?.notes ?? "");
  const [closedOn, setClosedOn] = useState(today);

  const onSuccess = () => {
    invalidate();
    onClose();
  };
  const create = useCreateLoan({ mutation: { onSuccess } });
  const replace = useReplaceLoan({ mutation: { onSuccess } });
  const mutation = replacing ? replace : create;

  const canSubmit =
    name.trim() !== "" &&
    lender.trim() !== "" &&
    Number(principal) > 0 &&
    principal.trim() !== "" &&
    rate.trim() !== "" &&
    Number(rate) >= 0 &&
    Number(payment) > 0 &&
    firstDue !== "" &&
    statementBalance.trim() !== "" &&
    Number(statementBalance) >= 0 &&
    statementDate !== "" &&
    (!replacing || closedOn !== "");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || mutation.isPending) return;
    const terms = {
      name: name.trim(),
      lender: lender.trim(),
      kind,
      principal: Number(principal),
      annual_rate: Number(rate),
      payment: Number(payment),
      term_months: term.trim() === "" ? null : Number(term),
      first_due_on: firstDue,
      statement_balance: Number(statementBalance),
      statement_balance_as_of: statementDate,
      notes: notes.trim(),
    };
    if (replacing) {
      replace.mutate({
        loanId: replacing.loan.id,
        data: { ...terms, closed_on: closedOn },
      });
    } else {
      create.mutate({ data: terms });
    }
  }

  const title = replacing ? "Replace at refinance" : "Record a loan";
  return (
    <form
      onSubmit={handleSubmit}
      className="flex max-h-[calc(90dvh-3rem)] flex-col"
    >
      <DialogHeader
        title={title}
        subtitle={
          replacing
            ? `Enter the new loan's terms. It needs its own name and payment tag; ${replacing.loan.name} closes on the date below.`
            : "A loan on the house, with its latest statement."
        }
        onClose={onClose}
      />
      <div className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto p-1">
        {replacing && (
          <label className={fieldLabelClass}>
            Old loan closes on
            <input
              type="date"
              value={closedOn}
              onChange={(e) => setClosedOn(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
        )}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className={fieldLabelClass}>
            Name
            <input
              value={name}
              placeholder={replacing ? "New loan name" : undefined}
              onChange={(e) => setName(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
          <label className={fieldLabelClass}>
            Lender
            <input
              value={lender}
              onChange={(e) => setLender(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
        </div>
        <label className={fieldLabelClass}>
          Kind
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as LoanKind)}
            className={cn("w-full", selectInputClass)}
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {LOAN_KIND_LABELS[k]}
              </option>
            ))}
          </select>
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className={fieldLabelClass}>
            Principal
            <input
              type="number"
              min={0.01}
              step="0.01"
              value={principal}
              onChange={(e) => setPrincipal(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
          <label className={fieldLabelClass}>
            Annual rate (%)
            <input
              type="number"
              min={0}
              step="0.001"
              value={rate}
              onChange={(e) => setRate(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
          <label className={fieldLabelClass}>
            Payment
            <input
              type="number"
              min={0.01}
              step="0.01"
              value={payment}
              onChange={(e) => setPayment(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
          <label className={fieldLabelClass}>
            Term (months, optional)
            <input
              type="number"
              min={1}
              step="1"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
        </div>
        <label className={fieldLabelClass}>
          First due date
          <input
            type="date"
            value={firstDue}
            onChange={(e) => setFirstDue(e.target.value)}
            className={cn("w-full", baseInputClass)}
          />
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className={fieldLabelClass}>
            Statement balance
            <input
              type="number"
              min={0}
              step="0.01"
              value={statementBalance}
              onChange={(e) => setStatementBalance(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
          <label className={fieldLabelClass}>
            Statement date
            <input
              type="date"
              value={statementDate}
              onChange={(e) => setStatementDate(e.target.value)}
              className={cn("w-full", baseInputClass)}
            />
          </label>
        </div>
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
            {errorMessage(mutation.error, "Failed to save the loan")}
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
          {title}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** Dialog to record a loan, or to replace one at a refinance. */
export function LoanDialog({
  open,
  replacing = null,
  onClose,
}: {
  open: boolean;
  replacing?: ReplacingLoan | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onClose={onClose}>
      {open && <LoanForm replacing={replacing} onClose={onClose} />}
    </Dialog>
  );
}
