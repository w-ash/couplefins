import { ChevronDown, Search, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CategoryGroupBreakdown } from "@/lib/reconciliation";
import type { TransactionFilters as TransactionFiltersType } from "@/lib/transaction-filters";
import { useClickOutside } from "@/lib/use-click-outside";
import { getPersonAccentColor } from "@/types/person";

// ─── Shared popover wrapper ───

function FilterPopover({
  trigger,
  children,
  onClose,
}: {
  trigger: React.ReactNode;
  children: (close: () => void) => React.ReactNode;
  onClose?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => {
    setOpen(false);
    onClose?.();
  }, [onClose]);
  useClickOutside(ref, open, close);

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen(!open)}>
        {trigger}
      </button>
      {open && (
        <div className="absolute left-0 top-full z-40 mt-1.5 min-w-56 overflow-hidden rounded-lg border border-border bg-popover shadow-lg">
          {children(close)}
        </div>
      )}
    </div>
  );
}

function FilterButton({ label, count }: { label: string; count: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg border border-input bg-card px-3 py-1.5 text-sm text-secondary-foreground shadow-sm transition-colors hover:bg-muted">
      {label}
      {count > 0 && (
        <span className="inline-flex size-5 items-center justify-center rounded-full bg-primary text-[11px] font-medium text-primary-foreground">
          {count}
        </span>
      )}
      <ChevronDown className="size-3.5 text-muted-foreground" />
    </span>
  );
}

// ─── Payer filter ───

export function PayerFilter({
  persons,
  activePayers,
  onChange,
}: {
  persons: Array<{ id: string; name: string }>;
  activePayers: string[];
  onChange: (payers: string[]) => void;
}) {
  const activeSet = useMemo(() => new Set(activePayers), [activePayers]);

  const toggle = useCallback(
    (id: string) => {
      const next = new Set(activeSet);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      // If all are selected, clear (= no filter)
      if (next.size === persons.length) onChange([]);
      else onChange([...next]);
    },
    [activeSet, persons.length, onChange],
  );

  return (
    <div className="flex items-center gap-1.5">
      {persons.map((p, i) => {
        const active = activeSet.size === 0 || activeSet.has(p.id);
        const color = getPersonAccentColor(i);
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => toggle(p.id)}
            className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
              active ? color : "bg-muted/50 text-muted-foreground/50"
            }`}
          >
            {p.name}
          </button>
        );
      })}
    </div>
  );
}

// ─── Category filter ───

export function CategoryFilter({
  breakdowns,
  activeCategories,
  onChange,
}: {
  breakdowns: CategoryGroupBreakdown[];
  activeCategories: string[];
  onChange: (categories: string[]) => void;
}) {
  const activeSet = useMemo(
    () => new Set(activeCategories),
    [activeCategories],
  );
  const [search, setSearch] = useState("");

  const toggleCategory = useCallback(
    (cat: string) => {
      const next = new Set(activeSet);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      onChange([...next]);
    },
    [activeSet, onChange],
  );

  const toggleGroup = useCallback(
    (group: CategoryGroupBreakdown) => {
      const cats = group.categories.map((c) => c.category);
      const allSelected = cats.every((c) => activeSet.has(c));
      const next = new Set(activeSet);
      for (const c of cats) {
        if (allSelected) next.delete(c);
        else next.add(c);
      }
      onChange([...next]);
    },
    [activeSet, onChange],
  );

  const q = search.toLowerCase();

  return (
    <FilterPopover
      trigger={
        <FilterButton label="Category" count={activeCategories.length} />
      }
      onClose={() => setSearch("")}
    >
      {() => (
        <div className="max-h-72 overflow-y-auto">
          <div className="sticky top-0 border-b border-border-muted bg-popover p-2">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter categories..."
                className="w-full rounded-md border border-input bg-card py-1 pl-7 pr-2 text-sm text-foreground placeholder:text-placeholder focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none"
              />
            </div>
          </div>
          <div className="p-1">
            {breakdowns.map((group) => {
              const visibleCats = group.categories.filter((c) =>
                c.category.toLowerCase().includes(q),
              );
              if (
                visibleCats.length === 0 &&
                !group.group_name.toLowerCase().includes(q)
              )
                return null;
              const groupCats = group.categories.map((c) => c.category);
              const allSelected = groupCats.every((c) => activeSet.has(c));
              const someSelected =
                !allSelected && groupCats.some((c) => activeSet.has(c));

              return (
                <div key={group.group_id ?? "uncat"}>
                  <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-sm font-medium text-popover-foreground hover:bg-accent">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      ref={(el) => {
                        if (el) el.indeterminate = someSelected;
                      }}
                      onChange={() => toggleGroup(group)}
                      className="accent-primary"
                    />
                    {group.group_name}
                  </label>
                  {visibleCats.map((cat) => (
                    <label
                      key={cat.category}
                      className="flex cursor-pointer items-center gap-2 rounded-md py-0.5 pl-7 pr-2 text-sm text-popover-foreground hover:bg-accent"
                    >
                      <input
                        type="checkbox"
                        checked={activeSet.has(cat.category)}
                        onChange={() => toggleCategory(cat.category)}
                        className="accent-primary"
                      />
                      {cat.category}
                    </label>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </FilterPopover>
  );
}

// ─── Tag filter ───

export function TagFilter({
  availableTags,
  activeTags,
  onChange,
}: {
  availableTags: string[];
  activeTags: string[];
  onChange: (tags: string[]) => void;
}) {
  const activeSet = useMemo(() => new Set(activeTags), [activeTags]);

  const toggle = useCallback(
    (tag: string) => {
      const next = new Set(activeSet);
      if (next.has(tag)) next.delete(tag);
      else next.add(tag);
      onChange([...next]);
    },
    [activeSet, onChange],
  );

  if (availableTags.length === 0) return null;

  return (
    <FilterPopover
      trigger={<FilterButton label="Tags" count={activeTags.length} />}
    >
      {() => (
        <div className="max-h-56 overflow-y-auto p-1">
          {availableTags.map((tag) => (
            <label
              key={tag}
              className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-sm text-popover-foreground hover:bg-accent"
            >
              <input
                type="checkbox"
                checked={activeSet.has(tag)}
                onChange={() => toggle(tag)}
                className="accent-primary"
              />
              {tag}
            </label>
          ))}
        </div>
      )}
    </FilterPopover>
  );
}

// ─── Amount range filter ───

export function AmountRangeFilter({
  minAmount,
  maxAmount,
  onChange,
}: {
  minAmount: number | null;
  maxAmount: number | null;
  onChange: (min: number | null, max: number | null) => void;
}) {
  const [localMin, setLocalMin] = useState(
    minAmount != null ? String(minAmount) : "",
  );
  const [localMax, setLocalMax] = useState(
    maxAmount != null ? String(maxAmount) : "",
  );

  // Sync from parent
  useEffect(() => {
    setLocalMin(minAmount != null ? String(minAmount) : "");
    setLocalMax(maxAmount != null ? String(maxAmount) : "");
  }, [minAmount, maxAmount]);

  const apply = useCallback(() => {
    const min = localMin ? Number(localMin) : null;
    const max = localMax ? Number(localMax) : null;
    onChange(min, max);
  }, [localMin, localMax, onChange]);

  const active = minAmount != null || maxAmount != null;

  return (
    <FilterPopover
      trigger={<FilterButton label="Amount" count={active ? 1 : 0} />}
    >
      {(close) => (
        <div className="w-52 p-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Filter by absolute amount
          </p>
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={localMin}
              onChange={(e) => setLocalMin(e.target.value)}
              placeholder="Min"
              className="w-full rounded-md border border-input bg-card px-2 py-1 text-sm text-foreground placeholder:text-placeholder focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none"
            />
            <span className="text-xs text-muted-foreground">to</span>
            <input
              type="number"
              value={localMax}
              onChange={(e) => setLocalMax(e.target.value)}
              placeholder="Max"
              className="w-full rounded-md border border-input bg-card px-2 py-1 text-sm text-foreground placeholder:text-placeholder focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none"
            />
          </div>
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                onChange(null, null);
                close();
              }}
              className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
            >
              Clear
            </button>
            <button
              type="button"
              onClick={() => {
                apply();
                close();
              }}
              className="rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
            >
              Apply
            </button>
          </div>
        </div>
      )}
    </FilterPopover>
  );
}

// ─── Active filter pills ───

interface ActiveFilter {
  key: string;
  label: string;
  onRemove: () => void;
}

export function ActiveFilterPills({
  filters,
  personNames,
}: {
  filters: TransactionFiltersType;
  personNames: Map<string, string>;
}) {
  const pills: ActiveFilter[] = [];

  if (filters.query) {
    pills.push({
      key: "query",
      label: `Search: "${filters.query}"`,
      onRemove: () => filters.setQuery(""),
    });
  }

  for (const p of filters.payers) {
    pills.push({
      key: `payer-${p}`,
      label: `Payer: ${personNames.get(p) ?? p}`,
      onRemove: () => filters.setPayers(filters.payers.filter((x) => x !== p)),
    });
  }

  for (const c of filters.categories) {
    pills.push({
      key: `cat-${c}`,
      label: c,
      onRemove: () =>
        filters.setCategories(filters.categories.filter((x) => x !== c)),
    });
  }

  for (const t of filters.tags) {
    pills.push({
      key: `tag-${t}`,
      label: `Tag: ${t}`,
      onRemove: () => filters.setTags(filters.tags.filter((x) => x !== t)),
    });
  }

  if (filters.minAmount != null || filters.maxAmount != null) {
    const parts: string[] = [];
    if (filters.minAmount != null) parts.push(`$${filters.minAmount}+`);
    if (filters.maxAmount != null) parts.push(`up to $${filters.maxAmount}`);
    pills.push({
      key: "amount",
      label: `Amount: ${parts.join(", ")}`,
      onRemove: () => filters.setAmountRange(null, null),
    });
  }

  if (pills.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {pills.map((pill) => (
        <span
          key={pill.key}
          className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary"
        >
          {pill.label}
          <button
            type="button"
            onClick={pill.onRemove}
            className="ml-0.5 rounded-full hover:bg-primary/20"
          >
            <X className="size-3" />
          </button>
        </span>
      ))}
      {pills.length > 1 && (
        <button
          type="button"
          onClick={filters.clearAll}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          Clear all
        </button>
      )}
    </div>
  );
}
