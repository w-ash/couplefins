import type {
  LedgerMonthResponse,
  LedgerSettlementResponse,
  LedgerYearResponse,
  MonthReference,
} from "@/api/generated/model";
import { currentYear } from "@/lib/format";

// Every number on Settle Up arrives precomputed from the API — this module
// only decides which slice of the ledger a view is looking at. No arithmetic
// on money.

/**
 * Selectable years, oldest first.
 *
 * The API guarantees every activity year plus the current year, so the served
 * list is trusted as-is; only an empty response falls back to the current year
 * to keep the default selection valid.
 */
export function ledgerYears(years: LedgerYearResponse[]): number[] {
  if (years.length === 0) return [currentYear()];
  return years.map((y) => y.year).sort((a, b) => a - b);
}

/**
 * The year the page should open on.
 *
 * The current year, which is what the couple is settling — except before it
 * has any activity at all (the January case), where opening on an empty year
 * would hide a balance left over from the year just ended. Then it falls back
 * to the oldest year still carrying a balance, or the newest with activity.
 */
export function defaultLedgerYear(years: LedgerYearResponse[]): number {
  const thisYear = currentYear();
  const hasActivity = (y: LedgerYearResponse) =>
    y.charged !== null || y.paid !== null;
  if (years.some((y) => y.year === thisYear && hasActivity(y))) {
    return thisYear;
  }
  const open = years.filter((y) => y.balance !== null);
  if (open.length > 0) return Math.min(...open.map((y) => y.year));
  const active = years.filter(hasActivity);
  if (active.length > 0) return Math.max(...active.map((y) => y.year));
  return thisYear;
}

/** The ledger entry for one calendar month, or null when it has no row. */
export function findMonth(
  months: LedgerMonthResponse[],
  year: number,
  month: number,
): LedgerMonthResponse | null {
  return months.find((m) => m.year === year && m.month === month) ?? null;
}

/**
 * The settlements whose recorded portions touch a year — or, with `month`,
 * one specific month.
 */
export function settlementsTouching(
  settlements: LedgerSettlementResponse[],
  year: number,
  month?: number,
): LedgerSettlementResponse[] {
  return settlements.filter((s) =>
    (s.portions ?? []).some(
      (p) => p.year === year && (month === undefined || p.month === month),
    ),
  );
}

/**
 * The month a payment settles: its oldest recorded portion, falling back to
 * the local month of `settled_at` when no portions were recorded.
 */
export function attributedMonth(s: LedgerSettlementResponse): MonthReference {
  const first = s.portions?.[0];
  if (first) return { year: first.year, month: first.month };
  const settled = new Date(s.settled_at);
  return { year: settled.getFullYear(), month: settled.getMonth() + 1 };
}
