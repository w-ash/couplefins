import { Plus, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { useClickOutside } from "@/lib/use-click-outside";

export interface ComboboxOption {
  value: string;
  label: string;
  group?: string;
}

interface ComboboxProps {
  mode: "single" | "multi";
  options: ComboboxOption[];
  value: string | string[];
  onChange: (value: string | string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  allowCreate?: boolean;
  className?: string;
}

export function Combobox({
  mode,
  options,
  value,
  onChange,
  placeholder,
  disabled = false,
  allowCreate = true,
  className,
}: ComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [focusedChipIndex, setFocusedChipIndex] = useState(-1);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxRef = useRef<HTMLDivElement>(null);

  const listboxId = useId();
  const optionIdPrefix = useId();

  // In single mode, sync input text with current value
  const singleLabel = useMemo(() => {
    if (mode !== "single" || typeof value !== "string") return "";
    return options.find((o) => o.value === value)?.label ?? value;
  }, [mode, value, options]);

  // Initialize query for single mode
  useEffect(() => {
    if (mode === "single") setQuery(singleLabel);
  }, [mode, singleLabel]);

  const selectedSet = useMemo(
    () => new Set(mode === "multi" ? (value as string[]) : []),
    [mode, value],
  );

  // Filter options
  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return options.filter((o) => {
      if (mode === "multi" && selectedSet.has(o.value)) return false;
      return !q || o.label.toLowerCase().includes(q);
    });
  }, [options, query, mode, selectedSet]);

  // Group filtered options for rendering
  const groups = useMemo(() => {
    const hasGroups = filtered.some((o) => o.group);
    if (!hasGroups) return [{ name: null, items: filtered }];

    const map = new Map<string, ComboboxOption[]>();
    for (const opt of filtered) {
      const g = opt.group ?? "Other";
      const arr = map.get(g);
      if (arr) arr.push(opt);
      else map.set(g, [opt]);
    }
    return [...map.entries()].map(([name, items]) => ({ name, items }));
  }, [filtered]);

  // Flat list of filtered options (for keyboard nav indexing)
  const flatFiltered = useMemo(() => groups.flatMap((g) => g.items), [groups]);

  // Should we show a "Create" option?
  const showCreate = useMemo(() => {
    if (!allowCreate || !query.trim()) return false;
    const q = query.trim().toLowerCase();
    return !options.some((o) => o.value.toLowerCase() === q);
  }, [allowCreate, query, options]);

  // Total navigable items (filtered + optional create)
  const totalItems = flatFiltered.length + (showCreate ? 1 : 0);

  const closeDropdown = useCallback(() => {
    setOpen(false);
    setHighlightedIndex(-1);
    if (mode === "single") setQuery(singleLabel);
  }, [mode, singleLabel]);

  useClickOutside(containerRef, open, closeDropdown);

  const selectOption = useCallback(
    (optValue: string) => {
      if (mode === "single") {
        onChange(optValue);
        closeDropdown();
      } else {
        const arr = value as string[];
        onChange([...arr, optValue]);
        setQuery("");
        setHighlightedIndex(-1);
        // Keep dropdown open in multi mode
      }
    },
    [mode, value, onChange, closeDropdown],
  );

  const createAndSelect = useCallback(() => {
    const trimmed = query.trim();
    if (!trimmed) return;
    selectOption(trimmed);
  }, [query, selectOption]);

  const removeChip = useCallback(
    (chipValue: string) => {
      if (mode !== "multi") return;
      const arr = value as string[];
      onChange(arr.filter((v) => v !== chipValue));
      setFocusedChipIndex(-1);
      inputRef.current?.focus();
    },
    [mode, value, onChange],
  );

  // Scroll highlighted option into view
  useEffect(() => {
    if (highlightedIndex < 0 || !listboxRef.current) return;
    const optionEl = listboxRef.current.querySelector(
      `[data-option-index="${highlightedIndex}"]`,
    );
    optionEl?.scrollIntoView({ block: "nearest" });
  }, [highlightedIndex]);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.nativeEvent instanceof InputEvent && e.nativeEvent.isComposing)
        return;
      setQuery(e.target.value);
      setHighlightedIndex(-1);
      setFocusedChipIndex(-1);
      if (!open) setOpen(true);
    },
    [open],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // Chip navigation (multi mode, input empty, dropdown closed)
      if (mode === "multi" && !open && !query) {
        const chips = value as string[];
        if (chips.length === 0) return;

        if (e.key === "Backspace" && focusedChipIndex === -1) {
          // First backspace: focus last chip
          setFocusedChipIndex(chips.length - 1);
          e.preventDefault();
          return;
        }
        if (focusedChipIndex >= 0) {
          if (e.key === "Backspace" || e.key === "Delete") {
            removeChip(chips[focusedChipIndex]);
            e.preventDefault();
            return;
          }
          if (e.key === "ArrowLeft" && focusedChipIndex > 0) {
            setFocusedChipIndex(focusedChipIndex - 1);
            e.preventDefault();
            return;
          }
          if (e.key === "ArrowRight") {
            if (focusedChipIndex < chips.length - 1) {
              setFocusedChipIndex(focusedChipIndex + 1);
            } else {
              setFocusedChipIndex(-1);
            }
            e.preventDefault();
            return;
          }
        }
      }

      // Clear chip focus when typing
      if (focusedChipIndex >= 0 && e.key.length === 1) {
        setFocusedChipIndex(-1);
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (!open) {
          setOpen(true);
          setHighlightedIndex(0);
        } else {
          setHighlightedIndex((prev) => (prev < totalItems - 1 ? prev + 1 : 0));
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (!open) {
          setOpen(true);
          setHighlightedIndex(totalItems - 1);
        } else {
          setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : totalItems - 1));
        }
      } else if (e.key === "Enter") {
        if (open && highlightedIndex >= 0) {
          e.preventDefault();
          e.stopPropagation();
          if (highlightedIndex < flatFiltered.length) {
            selectOption(flatFiltered[highlightedIndex].value);
          } else if (showCreate) {
            createAndSelect();
          }
        }
        // If dropdown closed, let Enter propagate to parent (form save)
      } else if (e.key === "Escape") {
        if (open) {
          e.preventDefault();
          e.stopPropagation();
          closeDropdown();
        }
        // If dropdown closed, let Escape propagate to parent (cancel edit)
      } else if (e.key === "Tab") {
        if (open) {
          closeDropdown();
        }
      } else if (e.key === "Home" && open) {
        e.preventDefault();
        setHighlightedIndex(0);
      } else if (e.key === "End" && open) {
        e.preventDefault();
        setHighlightedIndex(totalItems - 1);
      }
    },
    [
      mode,
      open,
      query,
      value,
      focusedChipIndex,
      highlightedIndex,
      totalItems,
      flatFiltered,
      showCreate,
      selectOption,
      createAndSelect,
      removeChip,
      closeDropdown,
    ],
  );

  const handleFocus = useCallback(() => {
    if (!open && !disabled) {
      setOpen(true);
      if (mode === "single") {
        // Select all text on focus so user can immediately type to filter
        setTimeout(() => inputRef.current?.select(), 0);
      }
    }
  }, [open, disabled, mode]);

  const highlightedOptionId =
    highlightedIndex >= 0 ? `${optionIdPrefix}-${highlightedIndex}` : undefined;

  // Precompute option-to-flat-index map for stable rendering
  const optionIndexMap = useMemo(() => {
    const map = new Map<string, number>();
    for (let i = 0; i < flatFiltered.length; i++) {
      map.set(flatFiltered[i].value, i);
    }
    return map;
  }, [flatFiltered]);

  return (
    <div ref={containerRef} className={`relative ${className ?? ""}`}>
      <div
        className={`flex flex-wrap items-center gap-1 rounded-md border bg-card px-2 py-1 text-sm shadow-sm ${
          disabled
            ? "border-input opacity-60"
            : open
              ? "border-ring ring-1 ring-ring"
              : "border-input"
        }`}
      >
        {/* Multi-mode chips */}
        {mode === "multi" &&
          (value as string[]).map((v, i) => (
            <span
              key={v}
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                focusedChipIndex === i
                  ? "bg-primary/20 text-primary ring-1 ring-primary"
                  : "bg-primary/10 text-primary"
              }`}
            >
              {v}
              <button
                type="button"
                tabIndex={-1}
                onClick={(e) => {
                  e.stopPropagation();
                  removeChip(v);
                }}
                disabled={disabled}
                className="rounded-full hover:bg-primary/20"
              >
                <X className="size-3" />
              </button>
            </span>
          ))}

        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-activedescendant={highlightedOptionId}
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          onCompositionEnd={() => {
            // After IME composition ends, open if we have query text
            if (query && !open) setOpen(true);
          }}
          placeholder={
            mode === "multi" && (value as string[]).length > 0
              ? undefined
              : placeholder
          }
          disabled={disabled}
          className="min-w-16 flex-1 bg-transparent text-foreground outline-none placeholder:text-placeholder"
        />
      </div>

      {/* Dropdown listbox */}
      {open && totalItems > 0 && (
        <div
          ref={listboxRef}
          id={listboxId}
          role="listbox"
          className="absolute left-0 top-full z-50 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border border-border bg-popover py-1 shadow-lg"
        >
          {groups.map((group) => {
            const header = group.name ? (
              <div
                key={`group-${group.name}`}
                role="presentation"
                className="px-2 pt-2 pb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground"
              >
                {group.name}
              </div>
            ) : null;

            const items = group.items.map((opt) => {
              const idx = optionIndexMap.get(opt.value) ?? -1;
              const isHighlighted = idx === highlightedIndex;
              const isSelected = mode === "single" && value === opt.value;
              return (
                <div
                  key={opt.value}
                  id={`${optionIdPrefix}-${idx}`}
                  role="option"
                  tabIndex={-1}
                  aria-selected={isSelected}
                  data-option-index={idx}
                  className={`flex cursor-pointer items-center gap-2 px-2 py-1.5 text-sm ${
                    isHighlighted
                      ? "bg-accent text-accent-foreground"
                      : "text-popover-foreground"
                  }`}
                  onMouseEnter={() => setHighlightedIndex(idx)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    selectOption(opt.value);
                  }}
                >
                  {opt.label}
                </div>
              );
            });

            return [header, ...items];
          })}

          {showCreate && (
            <div
              id={`${optionIdPrefix}-${flatFiltered.length}`}
              role="option"
              tabIndex={-1}
              aria-selected={false}
              data-option-index={flatFiltered.length}
              className={`flex cursor-pointer items-center gap-2 px-2 py-1.5 text-sm ${
                highlightedIndex === flatFiltered.length
                  ? "bg-accent text-accent-foreground"
                  : "text-popover-foreground"
              }`}
              onMouseEnter={() => setHighlightedIndex(flatFiltered.length)}
              onMouseDown={(e) => {
                e.preventDefault();
                createAndSelect();
              }}
            >
              <Plus className="size-3.5" />
              Create &ldquo;{query.trim()}&rdquo;
            </div>
          )}
        </div>
      )}

      {open && totalItems === 0 && query && (
        <div className="absolute left-0 top-full z-50 mt-1 w-full rounded-lg border border-border bg-popover px-3 py-2 text-sm text-muted-foreground shadow-lg">
          No matches
        </div>
      )}
    </div>
  );
}
