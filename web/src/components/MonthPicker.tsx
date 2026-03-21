import { Calendar } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { BottomSheet } from "@/components/BottomSheet";
import { MonthGrid } from "@/components/MonthGrid";
import { useIsMobile } from "@/hooks/useIsMobile";
import type { DateRange } from "@/lib/date-range";
import { isSingleMonth, monthStartEnd } from "@/lib/date-range";
import { MONTHS, useMonthYear } from "@/lib/format";
import { triggerButtonClass } from "@/lib/input-styles";
import { useClickOutside } from "@/lib/use-click-outside";

export function MonthPicker() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  const isMobile = useIsMobile();
  useClickOutside(ref, open && !isMobile, close);

  const { year, month } = useMonthYear();
  const [, setSearchParams] = useSearchParams();

  const label = `${MONTHS[month - 1]} ${year}`;

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
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="Select month"
        className={triggerButtonClass}
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
