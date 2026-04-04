import { Loader2 } from "lucide-react";
import { useEffect, useRef } from "react";
import type { SettlementCandidateResponse } from "@/api/generated/model";
import { useGetSettlementCandidates } from "@/api/generated/settlements/settlements";
import { InlineError } from "@/components/InlineError";
import { formatCurrency, formatDate } from "@/lib/format";
import { usePersonMaps } from "@/lib/persons";

function CandidateRow({
  candidate,
  checked,
  onToggle,
  getPersonName,
}: {
  candidate: SettlementCandidateResponse;
  checked: boolean;
  onToggle: () => void;
  getPersonName: (id: string) => string;
}) {
  const isPositive = candidate.amount >= 0;

  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-border-muted px-3 py-2.5 transition-colors hover:bg-muted/40 has-[:checked]:border-primary/40 has-[:checked]:bg-primary/5">
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        className="mt-0.5 size-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm font-medium text-foreground">
            {candidate.merchant}
          </span>
          <span className="shrink-0 text-sm tabular-nums text-foreground">
            {isPositive ? "+" : ""}
            {formatCurrency(candidate.amount)}
          </span>
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
          <span>{formatDate(candidate.date)}</span>
          <span aria-hidden="true">&middot;</span>
          <span>{getPersonName(candidate.payer_person_id)}</span>
        </div>
        {candidate.match_reasons.length > 0 && (
          <p className="mt-1 text-xs text-muted-foreground/70">
            {candidate.match_reasons.join(", ")}
          </p>
        )}
      </div>
    </label>
  );
}

export function CandidateChecklist({
  amount,
  month,
  year,
  persons,
  selectedIds,
  onSelectionChange,
}: {
  amount: string;
  month: number;
  year: number;
  persons: Array<{ id: string; name: string }>;
  selectedIds: string[];
  onSelectionChange: (ids: string[]) => void;
}) {
  const parsedAmount = Number.parseFloat(amount);
  const isValidAmount = !Number.isNaN(parsedAmount) && parsedAmount > 0;

  const {
    data: candidatesResponse,
    isLoading,
    isError,
  } = useGetSettlementCandidates(
    { year, month, amount: parsedAmount },
    { query: { enabled: isValidAmount, staleTime: 30_000 } },
  );
  const candidates =
    candidatesResponse?.status === 200 ? candidatesResponse.data : [];

  const { getPersonName } = usePersonMaps(persons);

  const prevAmountRef = useRef(amount);
  useEffect(() => {
    if (prevAmountRef.current !== amount) {
      prevAmountRef.current = amount;
      onSelectionChange([]);
    }
  }, [amount, onSelectionChange]);

  if (!isValidAmount) return null;

  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-medium text-foreground">
        Link bank transactions
      </legend>
      <p className="text-xs text-muted-foreground">
        When you pay via Venmo or Zelle, the transfer shows up as a separate
        transaction. Link it here so it's counted as a settlement, not spending.
      </p>

      {isLoading && (
        <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Searching for matches...
        </div>
      )}

      {isError && (
        <InlineError>Failed to load candidate transactions</InlineError>
      )}

      {!isLoading && !isError && candidates.length === 0 && (
        <p className="py-2 text-sm text-muted-foreground">
          No matching transfers found
        </p>
      )}

      {candidates.length > 0 && (
        <>
          <p className="text-xs font-medium text-muted-foreground">
            Found {candidates.length} matching{" "}
            {candidates.length === 1 ? "transfer" : "transfers"}
          </p>
          <div className="space-y-2">
            {candidates.map((c) => (
              <CandidateRow
                key={c.id}
                candidate={c}
                checked={selectedIds.includes(c.id)}
                onToggle={() => {
                  onSelectionChange(
                    selectedIds.includes(c.id)
                      ? selectedIds.filter((id) => id !== c.id)
                      : [...selectedIds, c.id],
                  );
                }}
                getPersonName={getPersonName}
              />
            ))}
          </div>
        </>
      )}
    </fieldset>
  );
}
