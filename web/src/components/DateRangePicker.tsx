import { Calendar, ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { DateRange as RdpDateRange } from "react-day-picker";
import { DayPicker } from "react-day-picker";
import type { DateRange } from "@/lib/date-range";
import {
  formatRangeLabel,
  lastMonth,
  lastYear,
  parseDate,
  thisMonth,
  toDateStr,
  yearToDate,
} from "@/lib/date-range";
import { useClickOutside } from "@/lib/use-click-outside";

const presets: Array<{ label: string; fn: () => DateRange }> = [
  { label: "This Month", fn: thisMonth },
  { label: "Last Month", fn: lastMonth },
  { label: "Year to Date", fn: yearToDate },
  { label: "Last Year", fn: lastYear },
];

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  setDateRange: (range: DateRange) => void;
}

export function DateRangePicker({
  startDate,
  endDate,
  setDateRange,
}: DateRangePickerProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useClickOutside(ref, open, close);

  // Track the in-progress range selection inside the popover
  const [pendingRange, setPendingRange] = useState<RdpDateRange | undefined>();

  // Reset pending range when popover opens
  useEffect(() => {
    if (open) {
      setPendingRange({ from: parseDate(startDate), to: parseDate(endDate) });
    }
  }, [open, startDate, endDate]);

  const applyPreset = useCallback(
    (fn: () => DateRange) => {
      setDateRange(fn());
      setOpen(false);
    },
    [setDateRange],
  );

  const handleRangeSelect = useCallback(
    (range: RdpDateRange | undefined) => {
      setPendingRange(range);
      if (range?.from && range?.to) {
        setDateRange({
          startDate: toDateStr(range.from),
          endDate: toDateStr(range.to),
        });
        setOpen(false);
      }
    },
    [setDateRange],
  );

  const label = formatRangeLabel(startDate, endDate);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="inline-flex items-center gap-2 rounded-lg border border-input bg-card px-3 py-1.5 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted"
      >
        <Calendar className="size-4 text-muted-foreground" />
        {label}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Choose date range"
          className="absolute right-0 top-full z-50 mt-2 flex overflow-hidden rounded-xl border border-border bg-popover shadow-lg"
        >
          {/* Presets */}
          <div className="flex w-36 flex-col gap-0.5 border-r border-border-muted p-2">
            <p className="mb-1 px-2 pt-1 text-[11px] font-medium tracking-wide text-muted-foreground/70 uppercase">
              Quick select
            </p>
            {presets.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => applyPreset(p.fn)}
                className="rounded-md px-2 py-1.5 text-left text-sm text-popover-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Calendar */}
          <div className="p-3">
            <DayPicker
              mode="range"
              selected={pendingRange}
              onSelect={handleRangeSelect}
              defaultMonth={parseDate(startDate)}
              numberOfMonths={2}
              showOutsideDays
              classNames={{
                months: "flex gap-4",
                month: "flex flex-col gap-2",
                month_caption: "flex justify-center items-center h-8",
                caption_label: "text-sm font-medium text-popover-foreground",
                nav: "flex items-center justify-between absolute inset-x-3 top-3",
                button_previous:
                  "size-7 inline-flex items-center justify-center rounded-md text-muted-foreground hover:bg-muted transition-colors",
                button_next:
                  "size-7 inline-flex items-center justify-center rounded-md text-muted-foreground hover:bg-muted transition-colors",
                weekdays: "flex",
                weekday:
                  "w-9 text-center text-xs font-medium text-muted-foreground/70",
                week: "flex",
                day: "relative size-9 text-center text-sm",
                day_button:
                  "relative inline-flex size-9 items-center justify-center rounded-md text-popover-foreground transition-colors hover:bg-accent",
                selected: "!bg-primary !text-primary-foreground !rounded-md",
                range_start:
                  "!bg-primary !text-primary-foreground !rounded-l-md !rounded-r-none",
                range_end:
                  "!bg-primary !text-primary-foreground !rounded-r-md !rounded-l-none",
                range_middle:
                  "!bg-primary/15 !text-popover-foreground !rounded-none",
                today: "font-bold",
                outside: "text-muted-foreground/40",
                disabled: "text-muted-foreground/30 cursor-not-allowed",
                chevron: "size-4",
                root: "relative",
              }}
              components={{
                Chevron: ({ orientation }) =>
                  orientation === "left" ? (
                    <ChevronLeft className="size-4" />
                  ) : (
                    <ChevronRight className="size-4" />
                  ),
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
