import { useState } from "react";
import { errorMessage } from "@/api/client";
import {
  useCloseLoan,
  useDeleteLoan,
  useUpdateLoanStatement,
} from "@/api/generated/house/house";
import type { LoanResponse } from "@/api/generated/model";
import { Button } from "@/components/Button";
import { Dialog, DialogFooter, DialogHeader } from "@/components/Dialog";
import { InlineError } from "@/components/InlineError";
import { useInvalidateHouse } from "@/hooks/useInvalidateHouse";
import { cn } from "@/lib/cn";
import { formatCurrency, localISODate } from "@/lib/format";
import { baseInputClass, fieldLabelClass } from "@/lib/input-styles";

function StatementForm({
  loan,
  onClose,
}: {
  loan: LoanResponse;
  onClose: () => void;
}) {
  const invalidate = useInvalidateHouse();
  const [balance, setBalance] = useState(String(loan.statement_balance));
  const [asOf, setAsOf] = useState(localISODate());
  const mutation = useUpdateLoanStatement({
    mutation: {
      onSuccess: () => {
        invalidate();
        onClose();
      },
    },
  });
  const canSubmit =
    balance.trim() !== "" && Number(balance) >= 0 && asOf !== "";

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSubmit) return;
        mutation.mutate({
          loanId: loan.id,
          data: { balance: Number(balance), as_of: asOf },
        });
      }}
    >
      <DialogHeader
        title="Update statement"
        subtitle={`The balance on the latest ${loan.name} statement.`}
        onClose={onClose}
      />
      <div className="mt-4 space-y-3">
        <label className={fieldLabelClass}>
          Balance
          <input
            type="number"
            min={0}
            step="0.01"
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
            className={cn("w-full", baseInputClass)}
          />
        </label>
        <label className={fieldLabelClass}>
          As of
          <input
            type="date"
            value={asOf}
            onChange={(e) => setAsOf(e.target.value)}
            className={cn("w-full", baseInputClass)}
          />
        </label>
      </div>
      {mutation.isError && (
        <div className="mt-3">
          <InlineError>
            {errorMessage(mutation.error, "Failed to update the statement")}
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
          Save statement
        </Button>
      </DialogFooter>
    </form>
  );
}

function CloseForm({
  loan,
  onClose,
}: {
  loan: LoanResponse;
  onClose: () => void;
}) {
  const invalidate = useInvalidateHouse();
  const [closedOn, setClosedOn] = useState(localISODate());
  const mutation = useCloseLoan({
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
        if (closedOn === "") return;
        mutation.mutate({ loanId: loan.id, data: { closed_on: closedOn } });
      }}
    >
      <DialogHeader
        title="Close loan"
        subtitle={`${loan.name} moves to past loans. Its history stays.`}
        onClose={onClose}
      />
      <div className="mt-4">
        <label className={fieldLabelClass}>
          Closed on
          <input
            type="date"
            value={closedOn}
            onChange={(e) => setClosedOn(e.target.value)}
            className={cn("w-full", baseInputClass)}
          />
        </label>
      </div>
      {mutation.isError && (
        <div className="mt-3">
          <InlineError>
            {errorMessage(mutation.error, "Failed to close the loan")}
          </InlineError>
        </div>
      )}
      <DialogFooter>
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={closedOn === ""}
          loading={mutation.isPending}
        >
          Close loan
        </Button>
      </DialogFooter>
    </form>
  );
}

function DeleteForm({
  loan,
  onClose,
}: {
  loan: LoanResponse;
  onClose: () => void;
}) {
  const invalidate = useInvalidateHouse();
  const mutation = useDeleteLoan({
    mutation: {
      onSuccess: () => {
        invalidate();
        onClose();
      },
    },
  });
  return (
    <>
      <DialogHeader
        title="Delete loan"
        subtitle={`${loan.name}, ${formatCurrency(loan.balance)} owed. A loan with linked payments cannot be deleted; close it instead.`}
        onClose={onClose}
      />
      {mutation.isError && (
        <div className="mt-3">
          <InlineError>
            {errorMessage(mutation.error, "Failed to delete the loan")}
          </InlineError>
        </div>
      )}
      <DialogFooter>
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="destructive"
          loading={mutation.isPending}
          onClick={() => mutation.mutate({ loanId: loan.id })}
        >
          Delete loan
        </Button>
      </DialogFooter>
    </>
  );
}

export type LoanAction = "statement" | "close" | "delete";

/** The small dialogs behind a loan card's statement, close and delete actions. */
export function LoanActionDialog({
  action,
  loan,
  onClose,
}: {
  action: LoanAction | null;
  loan: LoanResponse | null;
  onClose: () => void;
}) {
  const open = action !== null && loan !== null;
  return (
    <Dialog open={open} onClose={onClose} size="sm">
      {open && action === "statement" && (
        <StatementForm loan={loan} onClose={onClose} />
      )}
      {open && action === "close" && (
        <CloseForm loan={loan} onClose={onClose} />
      )}
      {open && action === "delete" && (
        <DeleteForm loan={loan} onClose={onClose} />
      )}
    </Dialog>
  );
}
