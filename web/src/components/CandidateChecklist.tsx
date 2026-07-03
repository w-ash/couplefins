import { ChevronDown, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type {
  MonthReference,
  SettlementCandidateResponse,
} from "@/api/generated/model";
import { useGetSettlementCandidates } from "@/api/generated/settlements/settlements";
import { InlineError } from "@/components/InlineError";
import { monthAtOrAfter, stepMonth } from "@/lib/date-range";
import { formatCurrency, formatDate, MONTHS } from "@/lib/format";
import { usePersonMaps } from "@/lib/persons";

const MAX_LINKED = 2;

function CandidateRow({
  candidate,
  checked,
  disabled,
  onToggle,
  getPersonName,
}: {
  candidate: SettlementCandidateResponse;
  checked: boolean;
  disabled: boolean;
  onToggle: () => void;
  getPersonName: (id: string) => string;
}) {
  const isPositive = candidate.amount >= 0;

  return (
    <label
      className={`flex items-start gap-3 rounded-lg border border-border-muted px-3 py-2.5 transition-colors has-[:checked]:border-primary/40 has-[:checked]:bg-primary/5 ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:bg-muted/40"}`}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={onToggle}
        className="mt-0.5 size-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed"
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

export type SelectedCandidate = Pick<
  SettlementCandidateResponse,
  "id" | "amount" | "merchant" | "payer_person_id"
>;

// Integer-cents arithmetic — a float sum of two transfers would persist
// dust like 20.369999999999997 and the month would never net to zero.
export function computeSettlementAmount(
  candidates: SelectedCandidate[],
): number {
  if (candidates.length === 0) return 0;
  const cents = (n: number) => Math.round(n * 100);
  const sumPositive = candidates
    .filter((c) => c.amount >= 0)
    .reduce((sum, c) => sum + cents(c.amount), 0);
  const sumAbsNegative = candidates
    .filter((c) => c.amount < 0)
    .reduce((sum, c) => sum + cents(Math.abs(c.amount)), 0);
  return Math.max(sumPositive, sumAbsNegative) / 100;
}

export function CandidateChecklist({
  amount,
  month,
  year,
  persons,
  selectedIds,
  onSelectionChange,
  latestTransactionMonth,
}: {
  amount: string;
  month: number;
  year: number;
  persons: Array<{ id: string; name: string }>;
  selectedIds: string[];
  onSelectionChange: (ids: string[], selected: SelectedCandidate[]) => void;
  latestTransactionMonth?: MonthReference | null;
}) {
  const parsedAmount = Number.parseFloat(amount);
  const isValidAmount = !Number.isNaN(parsedAmount) && parsedAmount > 0;

  const [searchYear, setSearchYear] = useState(year);
  const [searchMonth, setSearchMonth] = useState(month);

  const {
    data: candidatesResponse,
    isLoading,
    isError,
  } = useGetSettlementCandidates(
    {
      year,
      month,
      amount: parsedAmount,
      search_year: searchYear,
      search_month: searchMonth,
    },
    { query: { enabled: isValidAmount, staleTime: 30_000 } },
  );
  const candidates =
    candidatesResponse?.status === 200 ? candidatesResponse.data : [];

  const { getPersonName } = usePersonMaps(persons);

  const isAtFloor = searchYear === year && searchMonth === month;
  const ceiling = latestTransactionMonth ?? { year, month };
  const isAtCeiling =
    searchYear === ceiling.year && searchMonth === ceiling.month;

  const prevAmountRef = useRef(amount);
  useEffect(() => {
    if (prevAmountRef.current !== amount) {
      prevAmountRef.current = amount;
      onSelectionChange([], []);
      setShowAll(false);
      setSearchYear(year);
      setSearchMonth(month);
    }
  }, [amount, onSelectionChange, year, month]);

  const [showAll, setShowAll] = useState(false);

  const { paired, unpaired } = useMemo(() => {
    const sorted = [...candidates].sort(
      (a, b) => Math.abs(b.amount) - Math.abs(a.amount),
    );
    const amountCounts = new Map<number, number>();
    for (const c of sorted) {
      const key = Math.round(Math.abs(c.amount) * 100);
      amountCounts.set(key, (amountCounts.get(key) ?? 0) + 1);
    }
    const p: SettlementCandidateResponse[] = [];
    const u: SettlementCandidateResponse[] = [];
    for (const c of sorted) {
      const key = Math.round(Math.abs(c.amount) * 100);
      ((amountCounts.get(key) ?? 0) >= 2 ? p : u).push(c);
    }
    return { paired: p, unpaired: u };
  }, [candidates]);

  const visible = showAll ? [...paired, ...unpaired] : paired;

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

      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Searching:</span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled={isAtFloor}
            onClick={() => {
              const [ny, nm] = stepMonth(searchYear, searchMonth, -1);
              if (monthAtOrAfter(ny, nm, year, month)) {
                setSearchYear(ny);
                setSearchMonth(nm);
                setShowAll(false);
              }
            }}
            className="rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
            aria-label="Previous month"
          >
            <ChevronLeft className="size-3.5" />
          </button>
          <span className="min-w-24 text-center text-xs font-medium text-foreground">
            {MONTHS[searchMonth - 1]} {searchYear}
          </span>
          <button
            type="button"
            disabled={isAtCeiling}
            onClick={() => {
              const [ny, nm] = stepMonth(searchYear, searchMonth, 1);
              if (monthAtOrAfter(ceiling.year, ceiling.month, ny, nm)) {
                setSearchYear(ny);
                setSearchMonth(nm);
                setShowAll(false);
              }
            }}
            className="rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
            aria-label="Next month"
          >
            <ChevronRight className="size-3.5" />
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Searching for matches...
        </div>
      )}

      {isError && (
        <InlineError>Failed to load candidate transactions</InlineError>
      )}

      {!isLoading &&
        !isError &&
        paired.length === 0 &&
        unpaired.length === 0 && (
          <p className="py-2 text-sm text-muted-foreground">
            No matching transfers found
          </p>
        )}

      {visible.length > 0 && (
        <>
          <p className="text-xs font-medium text-muted-foreground">
            {paired.length > 0
              ? `${paired.length} matching ${paired.length === 1 ? "transfer" : "transfers"}`
              : `${unpaired.length} ${unpaired.length === 1 ? "transfer" : "transfers"} found`}
          </p>
          <div className="space-y-2">
            {visible.map((c) => {
              const isChecked = selectedIds.includes(c.id);
              return (
                <CandidateRow
                  key={c.id}
                  candidate={c}
                  checked={isChecked}
                  disabled={!isChecked && selectedIds.length >= MAX_LINKED}
                  onToggle={() => {
                    const nextIds = isChecked
                      ? selectedIds.filter((id) => id !== c.id)
                      : [...selectedIds, c.id];
                    const nextCandidates = candidates.filter((cn) =>
                      nextIds.includes(cn.id),
                    );
                    onSelectionChange(nextIds, nextCandidates);
                  }}
                  getPersonName={getPersonName}
                />
              );
            })}
          </div>
        </>
      )}

      {!showAll && unpaired.length > 0 && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronDown className="size-3.5" />
          {paired.length > 0
            ? `Show ${unpaired.length} more ${unpaired.length === 1 ? "transaction" : "transactions"}`
            : `Show ${unpaired.length} unmatched ${unpaired.length === 1 ? "transaction" : "transactions"}`}
        </button>
      )}
    </fieldset>
  );
}
