import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router";
import { MONTHS } from "./format";

export interface DateRange {
  startDate: string;
  endDate: string;
}

export function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function toDateStr(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function parseDate(s: string): Date {
  return new Date(`${s}T00:00:00`);
}

function lastDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function monthStartEnd(
  year: number,
  month: number,
): { startDate: string; endDate: string } {
  const last = lastDayOfMonth(year, month);
  return {
    startDate: `${year}-${pad(month)}-01`,
    endDate: `${year}-${pad(month)}-${pad(last)}`,
  };
}

export function thisMonth(): DateRange {
  const now = new Date();
  return monthStartEnd(now.getFullYear(), now.getMonth() + 1);
}

export function lastMonth(): DateRange {
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  return monthStartEnd(d.getFullYear(), d.getMonth() + 1);
}

export function yearToDate(): DateRange {
  const now = new Date();
  return {
    startDate: `${now.getFullYear()}-01-01`,
    endDate: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
  };
}

export function lastYear(): DateRange {
  const y = new Date().getFullYear() - 1;
  return { startDate: `${y}-01-01`, endDate: `${y}-12-31` };
}

export function isSingleMonth(
  startDate: string,
  endDate: string,
): { year: number; month: number } | null {
  const [sy, sm, sd] = startDate.split("-").map(Number);
  const [ey, em, ed] = endDate.split("-").map(Number);
  if (sy !== ey || sm !== em || sd !== 1) return null;
  const last = lastDayOfMonth(ey, em);
  if (ed !== last) return null;
  return { year: sy, month: sm };
}

const shortDateFmt = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

export function formatRangeLabel(startDate: string, endDate: string): string {
  const single = isSingleMonth(startDate, endDate);
  if (single) {
    return `${MONTHS[single.month - 1]} ${single.year}`;
  }
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  return `${shortDateFmt.format(start)} \u2013 ${shortDateFmt.format(end)}`;
}

export function useDateRange() {
  const [searchParams, setSearchParams] = useSearchParams();

  const { startDate, endDate } = useMemo(() => {
    const sd = searchParams.get("startDate");
    const ed = searchParams.get("endDate");
    if (sd && ed) return { startDate: sd, endDate: ed };
    // Fall back to year/month params for backward compat
    const y = searchParams.get("year");
    const m = searchParams.get("month");
    if (y && m) return monthStartEnd(Number(y), Number(m));
    return thisMonth();
  }, [searchParams]);

  const setDateRange = useCallback(
    (range: DateRange) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete("year");
          next.delete("month");
          next.set("startDate", range.startDate);
          next.set("endDate", range.endDate);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const singleMonth = useMemo(
    () => isSingleMonth(startDate, endDate),
    [startDate, endDate],
  );

  return { startDate, endDate, setDateRange, singleMonth };
}
