import { Calendar } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { BottomSheet } from "@/components/BottomSheet";
import { MonthGrid } from "@/components/MonthGrid";
import { useIsMobile } from "@/hooks/useIsMobile";
import { cn } from "@/lib/cn";
import type { DateRange } from "@/lib/date-range";
import { isSingleMonth, monthStartEnd } from "@/lib/date-range";
import { currentMonth, currentYear, MONTHS } from "@/lib/format";
import { triggerButtonClass } from "@/lib/input-styles";
import { useClickOutside } from "@/lib/use-click-outside";

/**
 * The month is always the caller's to supply — the page that owns the period
 * resolves it. Null means it is not known yet: the trigger stays mounted but
 * inert rather than showing today's date.
 */
export function MonthPicker({
  value,
}: {
  value: { year: number; month: number } | null;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  const isMobile = useIsMobile();
  useClickOutside(ref, open && !isMobile, close);

  const [, setSearchParams] = useSearchParams();

  const pending = value === null;
  // Today only anchors the (unreachable) grid while pending — the label says
  // "Loading month" rather than showing it.
  const { year, month } = value ?? {
    year: currentYear(),
    month: currentMonth(),
  };
  const label = pending ? "Loading month" : `${MONTHS[month - 1]} ${year}`;

  const { startDate, endDate } = useMemo(
    () => monthStartEnd(year, month),
    [year, month],
  );

  const handleSelect = useCallback(
    (range: DateRange) => {
      const selected = isSingleMonth(range.startDate, range.endDate);
      if (selected) {
        setSearchParams((prev) => {
          const next = new URLSearchParams(prev);
          next.set("year", String(selected.year));
          next.set("month", String(selected.month));
          return next;
        });
      }
      setOpen(false);
    },
    [setSearchParams],
  );

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        disabled={pending}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="Select month"
        className={cn(
          triggerButtonClass,
          "disabled:cursor-default disabled:text-muted-foreground",
        )}
      >
        <Calendar className="size-4 text-muted-foreground" />
        {label}
      </button>

      {open && isMobile && (
        <BottomSheet open onClose={close}>
          <MonthGrid
            startDate={startDate}
            endDate={endDate}
            onSelect={handleSelect}
            initialYear={year}
          />
        </BottomSheet>
      )}

      {open && !isMobile && (
        <div
          role="dialog"
          aria-label="Choose month"
          className="absolute right-0 top-full z-50 mt-1.5 overflow-hidden rounded-xl border border-border bg-popover p-4 shadow-lg"
        >
          <MonthGrid
            startDate={startDate}
            endDate={endDate}
            onSelect={handleSelect}
            initialYear={year}
          />
        </div>
      )}
    </div>
  );
}
