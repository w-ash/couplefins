import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";

interface TransactionSearchProps {
  value: string;
  onChange: (value: string) => void;
  filteredCount: number;
  totalCount: number;
}

export function TransactionSearch({
  value,
  onChange,
  filteredCount,
  totalCount,
}: TransactionSearchProps) {
  const [local, setLocal] = useState(value);

  // Sync external value changes (e.g. clearAll)
  useEffect(() => {
    setLocal(value);
  }, [value]);

  // Debounce local → parent
  useEffect(() => {
    if (local === value) return;
    const timer = setTimeout(() => onChange(local), 150);
    return () => clearTimeout(timer);
  }, [local, value, onChange]);

  const showCount = filteredCount !== totalCount;

  return (
    <div className="flex items-center gap-3">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          placeholder="Search transactions..."
          className="w-full rounded-lg border border-input bg-card py-2 pl-9 pr-9 text-sm text-foreground shadow-sm placeholder:text-placeholder focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none"
        />
        {local && (
          <button
            type="button"
            onClick={() => {
              setLocal("");
              onChange("");
            }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        )}
      </div>
      {showCount && (
        <p className="shrink-0 text-sm text-muted-foreground">
          Showing {filteredCount} of {totalCount}
        </p>
      )}
    </div>
  );
}
