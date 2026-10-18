import { AlertTriangle, Plus } from "lucide-react";
import { useState } from "react";
import { errorMessage } from "@/api/client";
import {
  useDeleteObligation,
  useListObligations,
  useMarkObligationPaid,
} from "@/api/generated/house/house";
import type {
  LoanResponse,
  ObligationResponse,
  ObligationStatus,
  PastLoanResponse,
} from "@/api/generated/model";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Dialog, DialogFooter, DialogHeader } from "@/components/Dialog";
import { MarkPaidDialog } from "@/components/house/MarkPaidDialog";
import {
  type EditingObligation,
  ObligationDialog,
} from "@/components/house/ObligationDialog";
import { InlineError } from "@/components/InlineError";
import { Pill } from "@/components/Pill";
import { SectionHeader } from "@/components/SectionHeader";
import { useInvalidateHouse } from "@/hooks/useInvalidateHouse";
import { cn } from "@/lib/cn";
import { formatCurrency, formatDate } from "@/lib/format";
import { OBLIGATION_KIND_LABELS, OBLIGATION_STATUS_LABELS } from "@/lib/house";
import { amountCellClass, cellClass, tableHeaderRowClass } from "@/lib/layout";

const STATUS_CLASSES: Record<ObligationStatus, string> = {
  due: "",
  late: "bg-negative/10 text-negative",
  paid: "bg-positive/10 text-positive",
};

function StatusPill({ status }: { status: ObligationStatus }) {
  return (
    <Pill className={STATUS_CLASSES[status]}>
      {OBLIGATION_STATUS_LABELS[status]}
    </Pill>
  );
}

function DeleteObligationDialog({
  obligation,
  onClose,
}: {
  obligation: ObligationResponse | null;
  onClose: () => void;
}) {
  const invalidate = useInvalidateHouse();
  const mutation = useDeleteObligation({
    mutation: {
      onSuccess: () => {
        invalidate();
        onClose();
      },
    },
  });
  return (
    <Dialog open={obligation !== null} onClose={onClose} size="sm">
      {obligation && (
        <>
          <DialogHeader
            title="Delete obligation"
            subtitle={`${obligation.name}, ${formatCurrency(obligation.amount)} due ${formatDate(obligation.due)}.`}
            onClose={onClose}
          />
          {mutation.isError && (
            <div className="mt-3">
              <InlineError>
                {errorMessage(
                  mutation.error,
                  "Failed to delete the obligation",
                )}
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
              onClick={() => mutation.mutate({ obligationId: obligation.id })}
            >
              Delete obligation
            </Button>
          </DialogFooter>
        </>
      )}
    </Dialog>
  );
}

function WhatCell({ o }: { o: ObligationResponse }) {
  return (
    <td className={cellClass}>
      <span className="font-medium">{o.name}</span>
      <span className="ml-2 text-xs text-muted-foreground">
        {OBLIGATION_KIND_LABELS[o.kind]}
      </span>
      {o.is_estimate && <Pill className="ml-2">estimate</Pill>}
    </td>
  );
}

function RecentlyPaid({
  paid,
  onUnmark,
  unmarking,
  error,
  example,
}: {
  paid: ObligationResponse[];
  onUnmark: (o: ObligationResponse) => void;
  unmarking: boolean;
  error: unknown;
  example: boolean;
}) {
  if (paid.length === 0) return null;
  return (
    <details className="mt-4" open={paid.length <= 3}>
      <summary className="cursor-pointer text-sm font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        Recently paid ({paid.length})
      </summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className={tableHeaderRowClass}>
              <th scope="col" className={cn(cellClass, "font-medium")}>
                What
              </th>
              <th scope="col" className={cn(cellClass, "font-medium")}>
                Status
              </th>
              <th scope="col" className={cn(cellClass, "font-medium")}>
                Due
              </th>
              <th scope="col" className={cn(amountCellClass, "font-medium")}>
                Amount
              </th>
              <th
                scope="col"
                className={cn(cellClass, "text-right font-medium")}
              >
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {paid.map((o) => (
              <tr key={o.id} className="border-b border-border/60 align-top">
                <WhatCell o={o} />
                <td className={cellClass}>
                  <StatusPill status={o.status} />
                </td>
                <td className={cn(cellClass, "whitespace-nowrap")}>
                  {formatDate(o.due)}
                </td>
                <td className={amountCellClass}>{formatCurrency(o.amount)}</td>
                <td className={cn(cellClass, "text-right")}>
                  {!example && (
                    <Button
                      variant="secondary"
                      size="sm"
                      className="min-h-11"
                      disabled={unmarking}
                      aria-label={`Unmark ${o.name}`}
                      onClick={() => onUnmark(o)}
                    >
                      Unmark
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {error != null && (
        <div className="mt-2">
          <InlineError>{errorMessage(error, "Failed to unmark")}</InlineError>
        </div>
      )}
    </details>
  );
}

export function UpcomingSection({
  upcoming,
  recentPaid,
  loans,
  pastLoans = [],
  example = false,
}: {
  example?: boolean;
  pastLoans?: PastLoanResponse[];
  upcoming: ObligationResponse[];
  recentPaid: ObligationResponse[];
  loans: LoanResponse[];
}) {
  const invalidate = useInvalidateHouse();
  const { data: res } = useListObligations();
  const records = res?.status === 200 ? res.data : [];
  const [recording, setRecording] = useState(false);
  const [editing, setEditing] = useState<EditingObligation | null>(null);
  const [marking, setMarking] = useState<ObligationResponse | null>(null);
  const [deleting, setDeleting] = useState<ObligationResponse | null>(null);
  const unmark = useMarkObligationPaid({
    mutation: { onSuccess: invalidate },
  });

  return (
    <Card as="section" aria-labelledby="house-upcoming">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionHeader
          example={example}
          id="house-upcoming"
          title="Upcoming"
          description="Obligations coming due and the bucket that pays each."
        />
        <Button
          variant="secondary"
          icon={<Plus className="size-4" />}
          onClick={() => setRecording(true)}
        >
          Record an obligation
        </Button>
      </div>
      {upcoming.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing coming due.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className={tableHeaderRowClass}>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  What
                </th>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Status
                </th>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Due
                </th>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Late after
                </th>
                <th scope="col" className={cn(cellClass, "font-medium")}>
                  Paid from
                </th>
                <th scope="col" className={cn(amountCellClass, "font-medium")}>
                  Amount
                </th>
                <th
                  scope="col"
                  className={cn(cellClass, "text-right font-medium")}
                >
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {upcoming.map((o) => (
                <tr key={o.id} className="border-b border-border/60 align-top">
                  <WhatCell o={o} />
                  <td className={cellClass}>
                    <StatusPill status={o.status} />
                  </td>
                  <td className={cn(cellClass, "whitespace-nowrap")}>
                    {formatDate(o.due)}
                  </td>
                  <td className={cn(cellClass, "whitespace-nowrap")}>
                    {o.late_after ? formatDate(o.late_after) : "—"}
                  </td>
                  <td className={cellClass}>{o.pays_from ?? "—"}</td>
                  <td className={amountCellClass}>
                    {formatCurrency(o.amount)}
                    {o.shortfall != null && (
                      <p className="mt-0.5 flex items-center justify-end gap-1 text-xs font-medium text-warning-muted-foreground">
                        <AlertTriangle className="size-3.5" aria-hidden />
                        Short by {formatCurrency(o.shortfall)}
                      </p>
                    )}
                  </td>
                  <td className={cn(cellClass, "text-right")}>
                    {!example && (
                      <div className="flex flex-wrap justify-end gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          className="min-h-11"
                          aria-label={`Mark ${o.name} paid`}
                          onClick={() => setMarking(o)}
                        >
                          Mark paid
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          className="min-h-11"
                          aria-label={`Edit ${o.name}`}
                          onClick={() =>
                            setEditing({
                              obligation: o,
                              record: records.find((r) => r.id === o.id),
                            })
                          }
                        >
                          Edit
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          className="min-h-11"
                          aria-label={`Delete ${o.name}`}
                          onClick={() => setDeleting(o)}
                        >
                          Delete
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <RecentlyPaid
        paid={recentPaid}
        unmarking={unmark.isPending}
        error={unmark.error}
        example={example}
        onUnmark={(o) =>
          unmark.mutate({ obligationId: o.id, data: { transaction_id: null } })
        }
      />
      <ObligationDialog
        open={recording}
        loans={loans}
        onClose={() => setRecording(false)}
      />
      <ObligationDialog
        open={editing !== null}
        editing={editing}
        loans={loans}
        pastLoans={pastLoans}
        onClose={() => setEditing(null)}
      />
      <MarkPaidDialog obligation={marking} onClose={() => setMarking(null)} />
      <DeleteObligationDialog
        obligation={deleting}
        onClose={() => setDeleting(null)}
      />
    </Card>
  );
}
