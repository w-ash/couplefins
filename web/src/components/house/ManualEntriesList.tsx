import { useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import {
  useDeleteManualEntry,
  useListManualEntries,
} from "@/api/generated/house/house";
import type { ManualEntryResponse } from "@/api/generated/model";
import { Button } from "@/components/Button";
import { Dialog, DialogFooter, DialogHeader } from "@/components/Dialog";
import { InlineError } from "@/components/InlineError";
import { Pill } from "@/components/Pill";
import { HOUSE_QUERY_KEYS } from "@/hooks/useRealtimeSync";
import { formatCurrency, formatDate } from "@/lib/format";
import { type Owner, SHARE_KIND_LABELS } from "@/lib/house";

function splitText(entry: ManualEntryResponse, owners: Owner[]): string {
  return owners
    .map((o, i) => {
      const pct = entry.owner_shares?.[o.id];
      return `${o.name} ${pct == null ? "—" : `${pct}%`}${i < owners.length - 1 ? "," : ""}`;
    })
    .join(" ");
}

function DeleteConfirm({
  entry,
  onClose,
}: {
  entry: ManualEntryResponse | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const mutation = useDeleteManualEntry({
    mutation: {
      onSuccess: () => {
        for (const queryKey of HOUSE_QUERY_KEYS) {
          queryClient.invalidateQueries({ queryKey });
        }
        onClose();
      },
    },
  });
  return (
    <Dialog open={entry !== null} onClose={onClose} size="sm">
      {entry && (
        <>
          <DialogHeader
            title="Delete credit"
            subtitle={`${entry.description}, ${formatCurrency(entry.amount)}. It leaves the shares.`}
            onClose={onClose}
          />
          {mutation.isError && (
            <div className="mt-3">
              <InlineError>
                {mutation.error instanceof Error
                  ? mutation.error.message
                  : "Failed to delete credit"}
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
              onClick={() => mutation.mutate({ transactionId: entry.id })}
            >
              Delete credit
            </Button>
          </DialogFooter>
        </>
      )}
    </Dialog>
  );
}

/** Credits recorded by hand, each with a delete action. */
export function ManualEntriesList({ owners }: { owners: Owner[] }) {
  const { data: res, isLoading } = useListManualEntries();
  const [pending, setPending] = useState<ManualEntryResponse | null>(null);
  const entries = res?.status === 200 ? res.data : [];

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading credits...</p>;
  }
  return (
    <>
      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No credits recorded by hand yet.
        </p>
      ) : (
        <ul className="divide-y divide-border/60">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="flex items-start justify-between gap-3 py-2.5"
            >
              <div className="min-w-0 space-y-0.5 text-sm">
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="text-muted-foreground tabular-nums">
                    {formatDate(entry.date)}
                  </span>
                  <span className="font-medium text-foreground">
                    {entry.description}
                  </span>
                  {entry.share_kind && (
                    <Pill>{SHARE_KIND_LABELS[entry.share_kind]}</Pill>
                  )}
                </p>
                <p className="text-xs text-muted-foreground">
                  {splitText(entry, owners)} · {entry.account_name}
                  {entry.document_ref && ` · ${entry.document_ref}`}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-sm font-medium tabular-nums">
                  {formatCurrency(entry.amount)}
                </span>
                <button
                  type="button"
                  onClick={() => setPending(entry)}
                  aria-label={`Delete ${entry.description}`}
                  className="flex min-h-11 min-w-11 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <DeleteConfirm entry={pending} onClose={() => setPending(null)} />
    </>
  );
}
