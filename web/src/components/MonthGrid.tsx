import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import type { DateRange } from "@/lib/date-range";
import { isSingleMonth, MONTHS_SHORT, monthStartEnd } from "@/lib/date-range";

interface MonthGridProps {
  startDate: string;
  endDate: string;
  onSelect: (range: DateRange) => void;
  initialYear: number;
}

export function MonthGrid({
  startDate,
  endDate,
  onSelect,
  initialYear,
}: MonthGridProps) {
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
          aria-label="Previous year"
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
          aria-label="Next year"
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
