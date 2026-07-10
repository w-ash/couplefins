import { Check, X } from "lucide-react";
import { Button } from "@/components/Button";
import { GenericToolResultCard } from "@/components/chat/ToolResultCard";
import type { ConfirmationState } from "@/lib/chat";
import { cn } from "@/lib/cn";
import { formatCurrency, SHORT_MONTHS, stripUserData } from "@/lib/format";

interface ConfirmationCardProps {
  actionId: string;
  description: string;
  details: Record<string, unknown>;
  toolName: string;
  state: ConfirmationState;
  onConfirm: (actionId: string) => void;
  onCancel: (actionId: string) => void;
}

// --- Detail renderers per tool type ---

function BudgetDetails({ details }: { details: Record<string, unknown> }) {
  return (
    <div className="space-y-0.5 text-xs text-muted-foreground">
      <p>
        <span className="font-medium text-foreground">
          {details.group_name as string}
        </span>{" "}
        &rarr;{" "}
        <span className="tabular-nums font-medium text-foreground">
          {formatCurrency(details.amount as number)}
        </span>
      </p>
      <p>
        {details.scope as string} &middot; {monthLabel(details)}
      </p>
    </div>
  );
}

function SplitDetails({ details }: { details: Record<string, unknown> }) {
  // Batch proposals carry only the splits list — the generic renderer's
  // table covers them; the bespoke layout below is for the single case.
  if (!("merchant" in details)) {
    return <GenericToolResultCard result={details} />;
  }
  return (
    <div className="space-y-0.5 text-xs text-muted-foreground">
      <p>
        <span className="font-medium text-foreground">
          {stripUserData(details.merchant as string)}
        </span>{" "}
        ({details.date as string}) &middot;{" "}
        <span className="tabular-nums">
          {formatCurrency(details.amount as number)}
        </span>
      </p>
      <p>
        Split: {details.current_split as string} &rarr;{" "}
        <span className="font-medium text-foreground">
          {details.new_split as string}
        </span>
      </p>
    </div>
  );
}

function BulkDetails({ details }: { details: Record<string, unknown> }) {
  const changes = details.changes as Record<string, unknown> | undefined;
  const count = details.count as number;

  return (
    <div className="space-y-0.5 text-xs text-muted-foreground">
      <p>
        <span className="font-medium text-foreground">
          {count} transaction{count !== 1 ? "s" : ""}
        </span>
      </p>
      {changes && (
        <ul className="list-inside list-disc">
          {"household" in changes && (
            <li>household = {String(changes.household)}</li>
          )}
          {"payer_percentage" in changes && (
            <li>
              split to {changes.payer_percentage as number}/
              {100 - (changes.payer_percentage as number)}
            </li>
          )}
          {"is_excluded" in changes && (
            <li>{changes.is_excluded ? "exclude" : "include"}</li>
          )}
          {"category" in changes && (
            <li>category &rarr; {changes.category as string}</li>
          )}
          {"tags" in changes && <TagChangeDetail tags={changes.tags} />}
        </ul>
      )}
    </div>
  );
}

function TagChangeDetail({ tags }: { tags: unknown }) {
  const info = tags as { action: string; values: string[] } | undefined;
  if (!info) return null;
  return (
    <li>
      {info.action} tags: {info.values.join(", ")}
    </li>
  );
}

function monthLabel(details: Record<string, unknown>): string {
  const month = details.month as number | undefined;
  const year = details.year as number | undefined;
  if (!month || !year) return "";
  return `${SHORT_MONTHS[month - 1]} ${year}`;
}

function DetailDisplay({
  toolName,
  details,
}: {
  toolName: string;
  details: Record<string, unknown>;
}) {
  switch (toolName) {
    case "update_budget":
      return <BudgetDetails details={details} />;
    case "update_transaction_split":
      return <SplitDetails details={details} />;
    case "bulk_update_transactions":
      return <BulkDetails details={details} />;
    default:
      // Anthropic's containment write-up measured ~93% of permission
      // prompts being rubber-stamped — concrete before/after details are
      // what make confirmation a real defense, so every mutation renders
      // its details, bespoke card or not.
      return <GenericToolResultCard result={details} />;
  }
}

// --- Main component ---

export function ConfirmationCard({
  actionId,
  description,
  details,
  toolName,
  state,
  onConfirm,
  onCancel,
}: ConfirmationCardProps) {
  const isPending = state === "pending";
  const isLoading = state === "loading";
  const isResolved = state === "confirmed" || state === "cancelled";

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card px-4 py-3",
        isResolved && "opacity-75",
      )}
    >
      <p className="mb-2 text-xs font-medium text-foreground">
        {stripUserData(description)}
      </p>

      <DetailDisplay toolName={toolName} details={details} />

      <div className="mt-3 flex items-center gap-2">
        {isResolved ? (
          <span
            className={cn(
              "inline-flex items-center gap-1 text-xs font-medium",
              state === "confirmed" ? "text-positive" : "text-muted-foreground",
            )}
          >
            {state === "confirmed" ? (
              <>
                <Check className="size-3.5" />
                Updated
              </>
            ) : (
              <>
                <X className="size-3.5" />
                Cancelled
              </>
            )}
          </span>
        ) : (
          <>
            <Button
              variant="primary"
              size="sm"
              loading={isLoading}
              loadingText="Confirming..."
              disabled={!isPending}
              onClick={() => onConfirm(actionId)}
            >
              Confirm
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={isLoading || !isPending}
              onClick={() => onCancel(actionId)}
            >
              Cancel
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
