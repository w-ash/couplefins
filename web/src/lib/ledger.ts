import type {
  LedgerMonthResponse,
  LedgerSettlementResponse,
  MonthSpanResponse,
  OwedAmountResponse,
} from "@/api/generated/model";
import { currentYear, isZeroCurrency } from "@/lib/format";

/** One calendar year's slice of the running settlement ledger. */
export interface LedgerYearSummary {
  year: number;
  /** Still unpaid from this year's months, direction-aware. */
  outstanding: OwedAmountResponse | null;
  /** This year's gross position, before any payments. */
  gross: OwedAmountResponse | null;
  /** Inclusive span of the year's months that still carry a balance. */
  span: MonthSpanResponse | null;
}

/**
 * Direction-aware sum of owed amounts over the two people involved.
 *
 * Returns null when the entries net to zero — a zero balance has no
 * meaningful direction.
 */
export function combineOwed(
  entries: OwedAmountResponse[],
): OwedAmountResponse | null {
  const anchor = entries.find((e) => !isZeroCurrency(e.amount));
  if (!anchor) return null;
  const signed = entries.reduce(
    (sum, e) =>
      sum + (e.from_person_id === anchor.from_person_id ? e.amount : -e.amount),
    0,
  );
  if (isZeroCurrency(signed)) return null;
  return signed > 0
    ? {
        amount: signed,
        from_person_id: anchor.from_person_id,
        to_person_id: anchor.to_person_id,
      }
    : {
        amount: -signed,
        from_person_id: anchor.to_person_id,
        to_person_id: anchor.from_person_id,
      };
}

/**
 * Aggregate the ledger rows falling in one calendar year.
 *
 * Per-month remainders come from the backend's FIFO application, so the
 * year summaries sum back to the all-time outstanding balance.
 */
export function summarizeLedgerYear(
  months: LedgerMonthResponse[],
  year: number,
): LedgerYearSummary {
  const inYear = months.flatMap((m) =>
    m.year === year && m.gross
      ? [{ month: m.month, gross: m.gross, remaining: m.remaining }]
      : [],
  );
  const open = inYear.filter((m) => !isZeroCurrency(m.remaining));
  const openMonths = open.map((m) => m.month);
  return {
    year,
    outstanding: combineOwed(
      open.map((m) => ({ ...m.gross, amount: m.remaining })),
    ),
    gross: combineOwed(inYear.map((m) => m.gross)),
    span:
      openMonths.length > 0
        ? {
            start: { year, month: Math.min(...openMonths) },
            end: { year, month: Math.max(...openMonths) },
          }
        : null,
  };
}

/**
 * Selectable years for the ledger, oldest first.
 *
 * The current year is always offered so the default selection exists even
 * before this year has any settlement activity.
 */
export function ledgerYears(months: LedgerMonthResponse[]): number[] {
  const years = new Set(months.map((m) => m.year));
  years.add(currentYear());
  return [...years].sort((a, b) => a - b);
}

/**
 * The year the page should open on.
 *
 * The current year, which is what the couple is settling — except before it
 * has any ledger rows at all (the January case), where opening on an empty
 * year would hide a balance carried over from the year just ended. Then it
 * falls back to the oldest year that still owes, or the newest with activity.
 */
export function defaultLedgerYear(months: LedgerMonthResponse[]): number {
  const thisYear = currentYear();
  if (months.length === 0 || months.some((m) => m.year === thisYear)) {
    return thisYear;
  }
  const open = months.filter((m) => !isZeroCurrency(m.remaining));
  return open.length > 0
    ? Math.min(...open.map((m) => m.year))
    : Math.max(...months.map((m) => m.year));
}

/**
 * The payments and waivers that belong to one calendar year.
 *
 * A payment belongs to the year(s) its FIFO coverage relieved — that is what
 * explains the year's balance. One that covered nothing (a reverse payment or
 * an overpayment credit) falls back to the year it was recorded in, so it is
 * never hidden entirely.
 */
export function settlementsForYear(
  settlements: LedgerSettlementResponse[],
  year: number,
): LedgerSettlementResponse[] {
  return settlements.filter((s) =>
    s.covered.length > 0
      ? s.covered.some((c) => c.year === year)
      : new Date(s.settled_at).getFullYear() === year,
  );
}
