import { useSearchParams } from "react-router";
import { currentYear, MONTHS, useMonthYear } from "@/lib/format";
import { selectInputClass } from "@/lib/input-styles";

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
        className={selectInputClass}
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
        className={selectInputClass}
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
