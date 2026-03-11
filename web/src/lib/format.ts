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

export function formatSplit(payerPercentage: number | null): string {
  const payer = payerPercentage ?? 50;
  return `${payer}/${100 - payer}`;
}

export function useMonthYear(): { year: number; month: number } {
  const [searchParams] = useSearchParams();
  return {
    year: Number(searchParams.get("year")) || currentYear(),
    month: Number(searchParams.get("month")) || currentMonth(),
  };
}
