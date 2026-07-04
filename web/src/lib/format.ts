import { useSearchParams } from "react-router";

export const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export const SHORT_MONTHS = MONTHS.map((m) => m.slice(0, 3));

export function currentYear(): number {
  return new Date().getFullYear();
}

export function currentMonth(): number {
  return new Date().getMonth() + 1;
}

// Local (browser) calendar date as YYYY-MM-DD — NOT `toISOString()`, which
// converts to UTC and can land on the wrong day for the entire US evening.
// Used to tell the backend what day it actually is for the user.
export function localISODate(d: Date = new Date()): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

const dateFmt = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
});

const dateTimeFmt = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

const currencyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function formatDate(dateStr: string): string {
  return dateFmt.format(new Date(`${dateStr}T00:00:00`));
}

// Short "Mon DD" format for an ISO timestamp (e.g. settlement.settled_at).
export function formatShortDate(iso: string): string {
  return dateFmt.format(new Date(iso));
}

export function formatDateTime(isoString: string): string {
  return dateTimeFmt.format(new Date(isoString));
}

export function formatCurrency(amount: number): string {
  return currencyFmt.format(amount);
}

// Half-cent: any amount within this of zero is indistinguishable from $0.00
// once formatted to two decimals. Use for "is this balance settled?" checks.
export const CURRENCY_EPSILON = 0.005;

export function isZeroCurrency(amount: number): boolean {
  return Math.abs(amount) < CURRENCY_EPSILON;
}

// Renders amounts with explicit + / − signs, except a near-zero value renders
// as $0.00. Uses the proper minus sign (U+2212), not a hyphen.
export function formatSignedCurrency(amount: number): string {
  if (isZeroCurrency(amount)) return formatCurrency(0);
  const sign = amount > 0 ? "+" : "−";
  return `${sign}${formatCurrency(Math.abs(amount))}`;
}

export function plural(word: string, count: number): string {
  return `${count} ${word}${count !== 1 ? "s" : ""}`;
}

export function amountColorClass(amount: number): string {
  return amount < 0 ? "text-negative" : "text-positive";
}

export function getDeltaColorClass(pct: number): string {
  if (pct <= 0) return "text-positive";
  if (pct > 25) return "text-destructive";
  return "text-foreground";
}

export function formatSplit(payerPercentage: number | null): string {
  return `${payerPercentage ?? 50}%`;
}

export function parsePercent(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return !Number.isNaN(parsed) && parsed >= 0 && parsed <= 100 ? parsed : null;
}

// Complementary rounding in integer cents, matching src/domain/splits.py:
// the payer share rounds half-up, the other share absorbs the remainder so
// the two always sum to the transaction amount.
export function computeShares(
  absAmount: number,
  payerPct: number,
): { payerShare: number; otherShare: number } {
  const totalCents = Math.round(absAmount * 100);
  const payerCents = Math.round((totalCents * payerPct) / 100);
  return {
    payerShare: payerCents / 100,
    otherShare: (totalCents - payerCents) / 100,
  };
}

interface SettlementShape {
  amount: number;
  from_person_id: string;
  to_person_id?: string;
}

export function buildSettlementLabel(
  settlement: SettlementShape | null,
  personNames: Map<string, string>,
  opts?: { settledLabel?: string; includeToName?: boolean },
): string {
  if (!settlement || settlement.amount === 0)
    return opts?.settledLabel ?? "Settled";
  const fromName = personNames.get(settlement.from_person_id) ?? "Unknown";
  if (opts?.includeToName && settlement.to_person_id) {
    const toName = personNames.get(settlement.to_person_id) ?? "";
    return `${fromName} owes ${toName} ${formatCurrency(settlement.amount)}`;
  }
  return `${fromName} owes ${formatCurrency(settlement.amount)}`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const relFmt = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export function formatRelativeTime(isoString: string): string {
  const thenDate = new Date(isoString);
  const diffSeconds = Math.round((thenDate.getTime() - Date.now()) / 1000);
  const absDiff = Math.abs(diffSeconds);

  if (absDiff < 60) return "just now";
  if (absDiff < 3600)
    return relFmt.format(Math.round(diffSeconds / 60), "minute");
  if (absDiff < 86400)
    return relFmt.format(Math.round(diffSeconds / 3600), "hour");
  if (absDiff < 2592000)
    return relFmt.format(Math.round(diffSeconds / 86400), "day");

  return dateFmt.format(thenDate);
}

export function formatDateRange(
  start: string | null,
  end: string | null,
): string | null {
  if (!start || !end) return null;
  const s = new Date(`${start}T00:00:00`);
  const e = new Date(`${end}T00:00:00`);
  const sMonth = SHORT_MONTHS[s.getMonth()];
  const eMonth = SHORT_MONTHS[e.getMonth()];
  if (sMonth === eMonth)
    return `${sMonth} ${s.getDate()}\u2009\u2013\u2009${e.getDate()}`;
  return `${sMonth} ${s.getDate()}\u2009\u2013\u2009${eMonth} ${e.getDate()}`;
}

export function useMonthYear(): { year: number; month: number } {
  const [searchParams] = useSearchParams();
  return {
    year: Number(searchParams.get("year")) || currentYear(),
    month: Number(searchParams.get("month")) || currentMonth(),
  };
}
