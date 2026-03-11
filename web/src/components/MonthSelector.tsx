import { useSearchParams } from "react-router";
import { currentYear, MONTHS, useMonthYear } from "@/lib/format";

function yearRange(): number[] {
  const now = currentYear();
  return Array.from({ length: 7 }, (_, i) => now - 3 + i);
}

export function MonthSelector() {
  const [, setSearchParams] = useSearchParams();
  const { year, month } = useMonthYear();

  function setParam(key: string, value: number) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set(key, String(value));
      return next;
    });
  }

  return (
    <div className="flex items-center gap-2">
      <select
        aria-label="Month"
        value={month}
        onChange={(e) => setParam("month", Number(e.target.value))}
        className="rounded-lg border border-input bg-card px-3 py-1.5 text-sm text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none"
      >
        {MONTHS.map((name, i) => (
          <option key={name} value={i + 1}>
            {name}
          </option>
        ))}
      </select>
      <select
        aria-label="Year"
        value={year}
        onChange={(e) => setParam("year", Number(e.target.value))}
        className="rounded-lg border border-input bg-card px-3 py-1.5 text-sm text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none"
      >
        {yearRange().map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </select>
    </div>
  );
}
