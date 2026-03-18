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

const dateFmt = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
});

const currencyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function formatDate(dateStr: string): string {
  return dateFmt.format(new Date(`${dateStr}T00:00:00`));
}

export function formatCurrency(amount: number): string {
  return currencyFmt.format(amount);
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
  const payer = payerPercentage ?? 50;
  return `${payer}/${100 - payer}`;
}

export function parsePercent(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return !Number.isNaN(parsed) && parsed >= 0 && parsed <= 100 ? parsed : null;
}

export function computeShares(
  absAmount: number,
  payerPct: number,
): { payerShare: number; otherShare: number } {
  return {
    payerShare: +((absAmount * payerPct) / 100).toFixed(2),
    otherShare: +((absAmount * (100 - payerPct)) / 100).toFixed(2),
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
