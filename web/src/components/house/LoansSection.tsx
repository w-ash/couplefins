import { Plus } from "lucide-react";
import { useState } from "react";
import { errorMessage } from "@/api/client";
import {
  useAddLoanPaymentObligations,
  useListLoans,
} from "@/api/generated/house/house";
import type { LoanResponse, PastLoanResponse } from "@/api/generated/model";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import {
  type LoanAction,
  LoanActionDialog,
} from "@/components/house/LoanActionDialogs";
import { LoanDialog } from "@/components/house/LoanDialog";
import { InlineError } from "@/components/InlineError";
import { InlineSuccess } from "@/components/InlineSuccess";
import { PersonBadge } from "@/components/PersonBadge";
import { Pill } from "@/components/Pill";
import { SectionHeader } from "@/components/SectionHeader";
import { StatsGrid } from "@/components/StatsGrid";
import { useInvalidateHouse } from "@/hooks/useInvalidateHouse";
import { cn } from "@/lib/cn";
import {
  formatCurrency,
  formatDate,
  formatPercent,
  plural,
} from "@/lib/format";
import { LOAN_KIND_LABELS, type Owner, ownerAmount } from "@/lib/house";
import { selectInputClass } from "@/lib/input-styles";
import { nestedCardClass } from "@/lib/layout";

const PAYMENT_COUNTS = Array.from({ length: 12 }, (_, i) => i + 1);

function AddPaymentsControl({ loan }: { loan: LoanResponse }) {
  const invalidate = useInvalidateHouse();
  const [months, setMonths] = useState(3);
  const [added, setAdded] = useState<number | null>(null);
  const mutation = useAddLoanPaymentObligations({
    mutation: {
      onSuccess: (res) => {
        invalidate();
        setAdded(res.status === 201 ? res.data.length : 0);
      },
    },
  });
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="sr-only" htmlFor={`payments-${loan.id}`}>
        Payments to add for {loan.name}
      </label>
      <select
        id={`payments-${loan.id}`}
        value={months}
        onChange={(e) => {
          setMonths(Number(e.target.value));
          setAdded(null);
        }}
        className={cn("w-20", selectInputClass)}
      >
        {PAYMENT_COUNTS.map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
      <Button
        variant="secondary"
        size="sm"
        className="min-h-11"
        loading={mutation.isPending}
        aria-label={`Add next ${months} payments for ${loan.name}`}
        onClick={() => {
          setAdded(null);
          mutation.mutate({ loanId: loan.id, data: { months } });
        }}
      >
        Add next {months} payments
      </Button>
      {added !== null &&
        (added > 0 ? (
          <InlineSuccess>Added {plural("payment", added)}</InlineSuccess>
        ) : (
          <span className="text-sm text-muted-foreground" role="status">
            Nothing to add
          </span>
        ))}
      {mutation.isError && (
        <InlineError>
          {errorMessage(mutation.error, "Failed to add payments")}
        </InlineError>
      )}
    </div>
  );
}

function PastLoans({
  pastLoans,
  loanName,
}: {
  pastLoans: PastLoanResponse[];
  loanName: (id: string) => string | undefined;
}) {
  if (pastLoans.length === 0) return null;
  return (
    <details className="mt-4 text-sm">
      <summary className="cursor-pointer font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        Past loans ({pastLoans.length})
      </summary>
      <ul className="mt-2 divide-y divide-border/60">
        {pastLoans.map((p) => {
          const replacement = p.replaced_by_loan_id
            ? loanName(p.replaced_by_loan_id)
            : undefined;
          return (
            <li key={p.id} className="py-2">
              <p className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-medium">{p.name}</span>
                <span className="text-muted-foreground">{p.lender}</span>
              </p>
              <p className="text-xs text-muted-foreground">
                Closed {formatDate(p.closed_on)}
                {replacement && ` · replaced by ${replacement}`}
              </p>
            </li>
          );
        })}
      </ul>
    </details>
  );
}

export function LoansSection({
  loans,
  pastLoans,
  owners,
  getPersonColor,
  example = false,
}: {
  example?: boolean;
  loans: LoanResponse[];
  pastLoans: PastLoanResponse[];
  owners: Owner[];
  getPersonColor: (id: string) => string;
}) {
  const { data: res } = useListLoans();
  const records = res?.status === 200 ? res.data : [];
  const [recording, setRecording] = useState(false);
  const [replacing, setReplacing] = useState<LoanResponse | null>(null);
  const [action, setAction] = useState<{
    kind: LoanAction;
    loan: LoanResponse;
  } | null>(null);

  const loanName = (id: string) =>
    [...loans, ...pastLoans].find((l) => l.id === id)?.name;

  return (
    <Card as="section" aria-labelledby="house-loans">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionHeader
          example={example}
          id="house-loans"
          title="Loans"
          description="What is owed on the house and who pays what."
        />
        <Button
          variant="secondary"
          icon={<Plus className="size-4" />}
          onClick={() => setRecording(true)}
        >
          Record a loan
        </Button>
      </div>
      {loans.length === 0 ? (
        <p className="text-sm text-muted-foreground">No loans recorded yet.</p>
      ) : (
        <div className="space-y-4">
          {loans.map((loan) => {
            const tag = records.find((r) => r.id === loan.id)?.tag;
            return (
              <div key={loan.id} className={nestedCardClass}>
                <div className="mb-3 flex flex-wrap items-baseline gap-x-2 gap-y-1">
                  <h3 className="font-medium text-foreground">{loan.name}</h3>
                  <span className="text-sm text-muted-foreground">
                    {loan.lender}
                  </span>
                  <Pill>{LOAN_KIND_LABELS[loan.kind]}</Pill>
                </div>
                <StatsGrid
                  stats={[
                    { label: "Balance", value: formatCurrency(loan.balance) },
                    {
                      label: "Rate",
                      value: formatPercent(loan.rate_percent, 2),
                    },
                    { label: "Payment", value: formatCurrency(loan.payment) },
                    {
                      label: "Next due",
                      value: loan.next_due ? formatDate(loan.next_due) : "—",
                    },
                  ]}
                />
                <p className="mt-2 text-xs text-muted-foreground">
                  Statement {formatCurrency(loan.statement_balance)} as of{" "}
                  {formatDate(loan.statement_balance_as_of)}
                </p>
                {tag && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Tag payments{" "}
                    <code className="font-mono text-foreground">{tag}</code>
                  </p>
                )}
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
                  <span className="text-xs font-medium text-muted-foreground">
                    Each owner's part
                  </span>
                  {owners.map((o) => (
                    <span key={o.id} className="flex items-center gap-2">
                      <PersonBadge
                        name={o.name}
                        accentColor={getPersonColor(o.id)}
                        size="xs"
                      />
                      <span className="text-sm tabular-nums">
                        {formatCurrency(ownerAmount(loan.owner_parts, o.id))}
                      </span>
                    </span>
                  ))}
                </div>
                {!example && (
                  <>
                    <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
                      <Button
                        variant="secondary"
                        size="sm"
                        className="min-h-11"
                        aria-label={`Update statement for ${loan.name}`}
                        onClick={() => setAction({ kind: "statement", loan })}
                      >
                        Update statement
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="min-h-11"
                        aria-label={`Replace ${loan.name} at refinance`}
                        onClick={() => setReplacing(loan)}
                      >
                        Replace at refinance
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="min-h-11"
                        aria-label={`Close ${loan.name}`}
                        onClick={() => setAction({ kind: "close", loan })}
                      >
                        Close loan
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="min-h-11"
                        aria-label={`Delete ${loan.name}`}
                        onClick={() => setAction({ kind: "delete", loan })}
                      >
                        Delete loan
                      </Button>
                    </div>
                    <div className="mt-3">
                      <AddPaymentsControl loan={loan} />
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
      <PastLoans pastLoans={pastLoans} loanName={loanName} />
      <LoanDialog open={recording} onClose={() => setRecording(false)} />
      <LoanDialog
        open={replacing !== null}
        replacing={
          replacing
            ? {
                loan: replacing,
                record: records.find((r) => r.id === replacing.id),
              }
            : null
        }
        onClose={() => setReplacing(null)}
      />
      <LoanActionDialog
        action={action?.kind ?? null}
        loan={action?.loan ?? null}
        onClose={() => setAction(null)}
      />
    </Card>
  );
}
