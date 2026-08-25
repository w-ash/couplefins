import { ChevronDown, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type {
  MonthReference,
  SettlementCandidateResponse,
} from "@/api/generated/model";
import { useGetSettlementCandidates } from "@/api/generated/settlements/settlements";
import { ExpandChevron } from "@/components/ExpandChevron";
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

// The legs are the authority on who paid whom: a negative leg's payer is
// the sender, a positive leg's payer the recipient. A single leg fills the
// other side with the other member of the couple. Contradictory legs
// (two senders, two recipients, or the same person on both sides) yield
// null — never a guess from the outstanding-balance direction.
export function deriveSettlementDirection(
  candidates: SelectedCandidate[],
  persons: Array<{ id: string }>,
): { from_person_id: string; to_person_id: string } | null {
  const senders = new Set(
    candidates.filter((c) => c.amount < 0).map((c) => c.payer_person_id),
  );
  const recipients = new Set(
    candidates.filter((c) => c.amount > 0).map((c) => c.payer_person_id),
  );
  if (senders.size > 1 || recipients.size > 1) return null;
  let from = senders.values().next().value ?? null;
  let to = recipients.values().next().value ?? null;
  if (from === null && to === null) return null;
  if (from === null) from = persons.find((p) => p.id !== to)?.id ?? null;
  if (to === null) to = persons.find((p) => p.id !== from)?.id ?? null;
  if (from === null || to === null || from === to) return null;
  return { from_person_id: from, to_person_id: to };
}

export function CandidateChecklist({
  amount,
  initialSearchMonth,
  searchFloor,
  persons,
  selectedIds,
  onSelectionChange,
  latestTransactionMonth,
  defaultExpanded = true,
}: {
  amount: string;
  // Concrete → the stepper starts on that month (post-hoc linking).
  // null → search the whole outstanding span; the stepper narrows on demand.
  initialSearchMonth: MonthReference | null;
  // Lowest month the stepper can reach — the outstanding span's start at
  // ledger level, the settlement's own month when linking post-hoc.
  searchFloor: MonthReference | null;
  persons: Array<{ id: string; name: string }>;
  selectedIds: string[];
  onSelectionChange: (ids: string[], selected: SelectedCandidate[]) => void;
  latestTransactionMonth?: MonthReference | null;
  // Collapsed start keeps the search out of the way until it is wanted —
  // the dialog, which exists to pick a transfer, opens expanded.
  defaultExpanded?: boolean;
}) {
  const parsedAmount = Number.parseFloat(amount);
  const isValidAmount = !Number.isNaN(parsedAmount) && parsedAmount > 0;

  const [search, setSearch] = useState<MonthReference | null>(
    initialSearchMonth,
  );

  const {
    data: candidatesResponse,
    isLoading,
    isError,
  } = useGetSettlementCandidates(
    {
      amount: parsedAmount,
      // Omitting the search month lets the backend search the whole
      // outstanding span.
      ...(search
        ? { search_year: search.year, search_month: search.month }
        : {}),
    },
    { query: { enabled: isValidAmount, staleTime: 30_000 } },
  );
  const candidates =
    candidatesResponse?.status === 200 ? candidatesResponse.data : [];

  const { getPersonName } = usePersonMaps(persons);

  const floor = searchFloor ?? initialSearchMonth;
  const ceiling = latestTransactionMonth ?? null;
  const isAtFloor =
    search !== null &&
    (floor === null ||
      (search.year === floor.year && search.month === floor.month));
  const isAtCeiling =
    search !== null &&
    ceiling !== null &&
    search.year === ceiling.year &&
    search.month === ceiling.month;
  // Stepping down from "all months" lands on the newest month in range.
  const narrowTarget = ceiling ?? floor;

  const prevAmountRef = useRef(amount);
  useEffect(() => {
    if (prevAmountRef.current !== amount) {
      prevAmountRef.current = amount;
      onSelectionChange([], []);
      setShowAll(false);
      setSearch(initialSearchMonth);
    }
  }, [amount, onSelectionChange, initialSearchMonth]);

  const [showAll, setShowAll] = useState(false);
  const [expanded, setExpanded] = useState(defaultExpanded);

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

  // One line that says what the collapsed body holds, so the disclosure is
  // worth opening (or safe to leave shut).
  const summary = isLoading
    ? "Searching for matches..."
    : paired.length > 0
      ? `${paired.length} matching ${paired.length === 1 ? "transfer" : "transfers"}`
      : unpaired.length > 0
        ? `${unpaired.length} ${unpaired.length === 1 ? "transfer" : "transfers"} found`
        : "No matching transfers found";

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

      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className="flex items-center gap-1.5 rounded text-xs font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ExpandChevron expanded={expanded} className="size-3.5" />
        {isLoading && <Loader2 className="size-3.5 animate-spin" />}
        {summary}
      </button>

      {isError && (
        <InlineError>Failed to load candidate transactions</InlineError>
      )}

      {expanded && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">Searching:</span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={
                  isAtFloor || (search === null && narrowTarget === null)
                }
                onClick={() => {
                  if (search === null) {
                    if (narrowTarget) {
                      setSearch(narrowTarget);
                      setShowAll(false);
                    }
                    return;
                  }
                  const [ny, nm] = stepMonth(search.year, search.month, -1);
                  if (
                    floor === null ||
                    monthAtOrAfter(ny, nm, floor.year, floor.month)
                  ) {
                    setSearch({ year: ny, month: nm });
                    setShowAll(false);
                  }
                }}
                className="rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
                aria-label="Previous month"
              >
                <ChevronLeft className="size-3.5" />
              </button>
              <span className="min-w-24 text-center text-xs font-medium text-foreground">
                {search
                  ? `${MONTHS[search.month - 1]} ${search.year}`
                  : "All months"}
              </span>
              <button
                type="button"
                // Bounded when the latest transaction month is known; unbounded
                // otherwise — the ceiling only covers household rows, so it can
                // be null while later-dated settlement candidates still exist.
                disabled={search === null || isAtCeiling}
                onClick={() => {
                  if (search === null) return;
                  const [ny, nm] = stepMonth(search.year, search.month, 1);
                  if (
                    ceiling === null ||
                    monthAtOrAfter(ceiling.year, ceiling.month, ny, nm)
                  ) {
                    setSearch({ year: ny, month: nm });
                    setShowAll(false);
                  }
                }}
                className="rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
                aria-label="Next month"
              >
                <ChevronRight className="size-3.5" />
              </button>
            </div>
            {initialSearchMonth === null && search !== null && (
              <button
                type="button"
                onClick={() => {
                  setSearch(null);
                  setShowAll(false);
                }}
                className="rounded text-xs text-primary transition-colors hover:text-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                All months
              </button>
            )}
          </div>

          {visible.length > 0 && (
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
        </div>
      )}
    </fieldset>
  );
}
