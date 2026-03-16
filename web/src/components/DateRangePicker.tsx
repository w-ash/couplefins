import { Calendar, ChevronLeft, ChevronRight, Grid3X3 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DateRange as RdpDateRange } from "react-day-picker";
import { DayPicker } from "react-day-picker";
import { SegmentedControl } from "@/components/SegmentedControl";
import type { DateRange } from "@/lib/date-range";
import {
  formatRangeLabel,
  isSingleMonth,
  lastMonth,
  lastThreeMonths,
  lastYear,
  MONTHS_SHORT,
  matchesPreset,
  monthStartEnd,
  parseDate,
  thisMonth,
  thisYear,
  toDateStr,
} from "@/lib/date-range";
import { selectInputClass } from "@/lib/input-styles";

import { useClickOutside } from "@/lib/use-click-outside";

// ─── Presets ───

const presets: Array<{ label: string; fn: () => DateRange }> = [
  { label: "This Month", fn: thisMonth },
  { label: "Last Month", fn: lastMonth },
  { label: "Last 3 Months", fn: lastThreeMonths },
  { label: "This Year", fn: thisYear },
  { label: "Last Year", fn: lastYear },
];

// ─── Preset sidebar ───

function Presets({
  startDate,
  endDate,
  onSelect,
}: {
  startDate: string;
  endDate: string;
  onSelect: (range: DateRange) => void;
}) {
  return (
    <div className="flex w-36 flex-col gap-0.5 border-r border-border-muted px-2 py-3">
      <p className="mb-1.5 px-2.5 text-xs font-medium tracking-wider text-muted-foreground/70 uppercase">
        Quick select
      </p>
      {presets.map((p) => {
        const active = matchesPreset(startDate, endDate, p.fn);
        return (
          <button
            key={p.label}
            type="button"
            onClick={() => onSelect(p.fn())}
            className={`rounded-md px-2.5 py-2 text-left text-sm transition-colors ${
              active
                ? "bg-accent font-medium text-accent-foreground"
                : "text-popover-foreground hover:bg-accent hover:text-accent-foreground"
            }`}
          >
            {p.label}
          </button>
        );
      })}
    </div>
  );
}

// ─── Month grid (4 x 3) ───

function MonthGrid({
  startDate,
  endDate,
  onSelect,
  initialYear,
}: {
  startDate: string;
  endDate: string;
  onSelect: (range: DateRange) => void;
  initialYear: number;
}) {
  const [year, setYear] = useState(initialYear);
  const selected = isSingleMonth(startDate, endDate);
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;

  return (
    <div className="flex min-w-64 flex-col gap-3">
      {/* Year navigation */}
      <div className="flex items-center justify-center gap-6">
        <button
          type="button"
          onClick={() => setYear((y) => y - 1)}
          className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted"
        >
          <ChevronLeft className="size-4" />
        </button>
        <span className="text-sm font-medium text-popover-foreground">
          {year}
        </span>
        <button
          type="button"
          onClick={() => setYear((y) => y + 1)}
          className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted"
        >
          <ChevronRight className="size-4" />
        </button>
      </div>

      {/* Month buttons */}
      <div className="grid grid-cols-4 gap-2">
        {MONTHS_SHORT.map((label, i) => {
          const month = i + 1;
          const isSelected =
            selected !== null &&
            selected.year === year &&
            selected.month === month;
          const isCurrentMonth = year === currentYear && month === currentMonth;

          return (
            <button
              key={label}
              type="button"
              onClick={() => onSelect(monthStartEnd(year, month))}
              className={`rounded-lg py-2.5 text-center text-sm transition-colors ${
                isSelected
                  ? "bg-primary font-medium text-primary-foreground"
                  : isCurrentMonth
                    ? "font-bold text-popover-foreground hover:bg-accent"
                    : "text-popover-foreground hover:bg-accent"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Calendar range picker ───

const CALENDAR_START = new Date(2024, 0);
const CALENDAR_END = new Date(2027, 11);

function CalendarRange({
  startDate,
  endDate,
  onRangeChange,
}: {
  startDate: string;
  endDate: string;
  onRangeChange: (range: DateRange) => void;
}) {
  const [pendingRange, setPendingRange] = useState<RdpDateRange | undefined>(
    () => ({
      from: parseDate(startDate),
      to: parseDate(endDate),
    }),
  );

  // Sync pending range when external dates change
  useEffect(() => {
    setPendingRange({ from: parseDate(startDate), to: parseDate(endDate) });
  }, [startDate, endDate]);

  const handleSelect = useCallback(
    (range: RdpDateRange | undefined) => {
      setPendingRange(range);
      if (range?.from && range?.to) {
        onRangeChange({
          startDate: toDateStr(range.from),
          endDate: toDateStr(range.to),
        });
      }
    },
    [onRangeChange],
  );

  return (
    <DayPicker
      mode="range"
      selected={pendingRange}
      onSelect={handleSelect}
      defaultMonth={parseDate(startDate)}
      numberOfMonths={2}
      fixedWeeks
      startMonth={CALENDAR_START}
      endMonth={CALENDAR_END}
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
        weekday: "w-9 text-center text-xs font-medium text-muted-foreground/70",
        week: "flex",
        day: "relative size-9 text-center text-sm",
        day_button:
          "relative inline-flex size-9 items-center justify-center rounded-md text-popover-foreground transition-colors hover:bg-accent",
        selected:
          "[&>button]:bg-primary [&>button]:text-primary-foreground [&>button]:rounded-md",
        range_start:
          "[&>button]:bg-primary [&>button]:text-primary-foreground [&>button]:rounded-l-md [&>button]:rounded-r-none",
        range_end:
          "[&>button]:bg-primary [&>button]:text-primary-foreground [&>button]:rounded-r-md [&>button]:rounded-l-none",
        range_middle:
          "[&>button]:bg-primary/15 [&>button]:text-popover-foreground [&>button]:rounded-none",
        today: "[&>button]:font-bold",
        disabled:
          "[&>button]:text-muted-foreground/30 [&>button]:cursor-not-allowed",
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
  );
}

// ─── Date input fields ───

const dateInputClass = `w-[7.5rem] tabular-nums ${selectInputClass}`;

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function isValidDateStr(s: string): boolean {
  if (!DATE_RE.test(s)) return false;
  const d = parseDate(s);
  return toDateStr(d) === s;
}

function DateInputFields({
  startDate,
  endDate,
  onRangeChange,
}: {
  startDate: string;
  endDate: string;
  onRangeChange: (range: DateRange) => void;
}) {
  const [start, setStart] = useState(startDate);
  const [end, setEnd] = useState(endDate);

  // Sync when external dates change (e.g. from calendar or preset)
  useEffect(() => {
    setStart(startDate);
    setEnd(endDate);
  }, [startDate, endDate]);

  const commitStart = useCallback(() => {
    if (isValidDateStr(start) && start <= end) {
      onRangeChange({ startDate: start, endDate: end });
    } else {
      setStart(startDate);
    }
  }, [start, end, startDate, onRangeChange]);

  const commitEnd = useCallback(() => {
    if (isValidDateStr(end) && start <= end) {
      onRangeChange({ startDate: start, endDate: end });
    } else {
      setEnd(endDate);
    }
  }, [start, end, endDate, onRangeChange]);

  const handleKeyDown = useCallback(
    (commit: () => void) => (e: React.KeyboardEvent) => {
      if (e.key === "Enter") commit();
    },
    [],
  );

  return (
    <div className="flex items-center gap-2.5">
      <input
        type="text"
        value={start}
        onChange={(e) => setStart(e.target.value)}
        onBlur={commitStart}
        onKeyDown={handleKeyDown(commitStart)}
        placeholder="YYYY-MM-DD"
        className={dateInputClass}
      />
      <span className="text-xs text-muted-foreground/50">to</span>
      <input
        type="text"
        value={end}
        onChange={(e) => setEnd(e.target.value)}
        onBlur={commitEnd}
        onKeyDown={handleKeyDown(commitEnd)}
        placeholder="YYYY-MM-DD"
        className={dateInputClass}
      />
    </div>
  );
}

// ─── Orchestrator ───

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
  const [view, setView] = useState<"months" | "calendar">("months");
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useClickOutside(ref, open, close);

  const label = formatRangeLabel(startDate, endDate);

  // Default the month grid to the year of the current start date
  const gridYear = useMemo(
    () =>
      Number.parseInt(startDate.slice(0, 4), 10) || new Date().getFullYear(),
    [startDate],
  );

  const applyAndClose = useCallback(
    (range: DateRange) => {
      setDateRange(range);
      setOpen(false);
    },
    [setDateRange],
  );

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
          className="absolute right-0 top-full z-50 mt-1.5 flex overflow-hidden rounded-xl border border-border bg-popover shadow-lg"
        >
          {/* Left: Presets */}
          <Presets
            startDate={startDate}
            endDate={endDate}
            onSelect={applyAndClose}
          />

          {/* Right: View toggle + content + date inputs */}
          <div className="flex flex-col gap-3 p-4">
            {/* View toggle */}
            <SegmentedControl
              options={[
                {
                  value: "months",
                  label: "Months",
                  icon: <Grid3X3 className="size-3" />,
                },
                {
                  value: "calendar",
                  label: "Calendar",
                  icon: <Calendar className="size-3" />,
                },
              ]}
              value={view}
              onChange={setView}
              size="sm"
            />

            {/* Content */}
            {view === "months" ? (
              <MonthGrid
                startDate={startDate}
                endDate={endDate}
                onSelect={applyAndClose}
                initialYear={gridYear}
              />
            ) : (
              <CalendarRange
                startDate={startDate}
                endDate={endDate}
                onRangeChange={setDateRange}
              />
            )}

            {/* Date input fields */}
            <div className="mt-1 border-t border-border-muted pt-3">
              <DateInputFields
                startDate={startDate}
                endDate={endDate}
                onRangeChange={setDateRange}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
