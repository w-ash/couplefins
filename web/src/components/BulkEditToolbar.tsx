import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { Combobox, type ComboboxOption } from "@/components/Combobox";
import { percentInputClass } from "@/components/SplitEditor";
import type {
  BulkModifyTagsPayload,
  BulkUpdatePayload,
  SplitUpdate,
} from "@/lib/transactions";

type Panel = "split" | "category" | "tags" | null;

interface BulkEditToolbarProps {
  selectedIds: Set<string>;
  selectedTagCounts: Map<string, number>;
  categoryOptions: ComboboxOption[];
  availableTags: string[];
  saving: boolean;
  onApplySplit: (splits: SplitUpdate[]) => void;
  onApplyBulkUpdate: (payload: BulkUpdatePayload) => void;
  onApplyBulkTags: (payload: BulkModifyTagsPayload) => void;
  onCancel: () => void;
}

function TabButton({
  active,
  disabled,
  onClick,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
        active
          ? "bg-card text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function SplitPanel({
  selectedCount,
  saving,
  onApply,
}: {
  selectedCount: number;
  saving: boolean;
  onApply: (percentage: number) => void;
}) {
  const [value, setValue] = useState("50");
  const inputRef = useRef<HTMLInputElement>(null);
  const parsed = Number.parseInt(value, 10);
  const isValid = !Number.isNaN(parsed) && parsed >= 0 && parsed <= 100;

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && isValid) {
        onApply(parsed);
      }
    },
    [isValid, parsed, onApply],
  );

  return (
    <div className="flex items-center gap-3">
      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        <span>Set split to</span>
        <input
          ref={inputRef}
          type="number"
          min={0}
          max={100}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          className={percentInputClass}
          disabled={saving}
        />
        <span>%</span>
      </label>
      <Button
        size="sm"
        onClick={() => onApply(parsed)}
        disabled={!isValid || selectedCount === 0 || saving}
        loading={saving}
        loadingText="Applying"
      >
        Apply to {selectedCount}
      </Button>
    </div>
  );
}

function CategoryPanel({
  selectedCount,
  categoryOptions,
  saving,
  onApply,
}: {
  selectedCount: number;
  categoryOptions: ComboboxOption[];
  saving: boolean;
  onApply: (category: string) => void;
}) {
  const [selected, setSelected] = useState("");

  return (
    <div className="flex items-center gap-3">
      <Combobox
        mode="single"
        options={categoryOptions}
        value={selected}
        onChange={(v) => setSelected(v as string)}
        placeholder="Select category"
        disabled={saving}
        allowCreate={false}
        className="w-64"
      />
      <Button
        size="sm"
        onClick={() => onApply(selected)}
        disabled={!selected || selectedCount === 0 || saving}
        loading={saving}
        loadingText="Applying"
      >
        Apply to {selectedCount}
      </Button>
    </div>
  );
}

function TagsPanel({
  selectedCount,
  selectedTagCounts,
  availableTags,
  saving,
  onApply,
}: {
  selectedCount: number;
  selectedTagCounts: Map<string, number>;
  availableTags: string[];
  saving: boolean;
  onApply: (action: "add" | "remove", tags: string[]) => void;
}) {
  const [action, setAction] = useState<"add" | "remove">("add");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  const switchAction = useCallback(
    (newAction: "add" | "remove") => {
      if (newAction !== action) {
        setAction(newAction);
        setSelectedTags([]);
      }
    },
    [action],
  );

  const tagOptions: ComboboxOption[] = useMemo(() => {
    if (action === "remove") {
      return [...selectedTagCounts.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([tag, count]) => ({
          value: tag,
          label:
            count < selectedCount ? `${tag} (${count}/${selectedCount})` : tag,
        }));
    }
    return availableTags.map((tag) => {
      const count = selectedTagCounts.get(tag) ?? 0;
      if (count > 0 && count < selectedCount) {
        return {
          value: tag,
          label: `${tag} — on ${count} of ${selectedCount}`,
        };
      }
      if (count === selectedCount) {
        return { value: tag, label: `${tag} (all)` };
      }
      return { value: tag, label: tag };
    });
  }, [action, availableTags, selectedTagCounts, selectedCount]);

  return (
    <div className="flex items-center gap-3">
      <div className="flex rounded-full border border-border bg-muted/50 p-0.5">
        <button
          type="button"
          onClick={() => switchAction("add")}
          className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
            action === "add"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground"
          }`}
        >
          Add
        </button>
        <button
          type="button"
          onClick={() => switchAction("remove")}
          className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
            action === "remove"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground"
          }`}
        >
          Remove
        </button>
      </div>
      <Combobox
        mode="multi"
        options={tagOptions}
        value={selectedTags}
        onChange={(v) => setSelectedTags(v as string[])}
        placeholder="Select tags"
        disabled={saving}
        allowCreate={action === "add"}
        className="w-64"
      />
      <Button
        size="sm"
        onClick={() => onApply(action, selectedTags)}
        disabled={selectedTags.length === 0 || selectedCount === 0 || saving}
        loading={saving}
        loadingText="Applying"
      >
        Apply to {selectedCount}
      </Button>
    </div>
  );
}

export function BulkEditToolbar({
  selectedIds,
  selectedTagCounts,
  categoryOptions,
  availableTags,
  saving,
  onApplySplit,
  onApplyBulkUpdate,
  onApplyBulkTags,
  onCancel,
}: BulkEditToolbarProps) {
  const [activePanel, setActivePanel] = useState<Panel>("split");
  const count = selectedIds.size;
  const ids = useMemo(() => [...selectedIds], [selectedIds]);

  const handleSplit = useCallback(
    (percentage: number) => {
      onApplySplit(
        ids.map((id) => ({ transaction_id: id, payer_percentage: percentage })),
      );
    },
    [ids, onApplySplit],
  );

  const handleCategory = useCallback(
    (category: string) => {
      onApplyBulkUpdate({ transaction_ids: ids, category });
    },
    [ids, onApplyBulkUpdate],
  );

  const handleTags = useCallback(
    (action: "add" | "remove", tags: string[]) => {
      onApplyBulkTags({ transaction_ids: ids, action, tags });
    },
    [ids, onApplyBulkTags],
  );

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/50 px-4 py-3">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-foreground">
          {count} selected
        </span>

        <div className="flex gap-1">
          <TabButton
            active={activePanel === "split"}
            disabled={saving}
            onClick={() =>
              setActivePanel(activePanel === "split" ? null : "split")
            }
          >
            Split
          </TabButton>
          <TabButton
            active={activePanel === "category"}
            disabled={saving}
            onClick={() =>
              setActivePanel(activePanel === "category" ? null : "category")
            }
          >
            Category
          </TabButton>
          <TabButton
            active={activePanel === "tags"}
            disabled={saving}
            onClick={() =>
              setActivePanel(activePanel === "tags" ? null : "tags")
            }
          >
            Tags
          </TabButton>
        </div>

        <div className="ml-auto">
          <Button
            variant="secondary"
            size="sm"
            onClick={onCancel}
            disabled={saving}
          >
            Cancel
          </Button>
        </div>
      </div>

      {activePanel === "split" && (
        <SplitPanel
          selectedCount={count}
          saving={saving}
          onApply={handleSplit}
        />
      )}
      {activePanel === "category" && (
        <CategoryPanel
          selectedCount={count}
          categoryOptions={categoryOptions}
          saving={saving}
          onApply={handleCategory}
        />
      )}
      {activePanel === "tags" && (
        <TagsPanel
          selectedCount={count}
          selectedTagCounts={selectedTagCounts}
          availableTags={availableTags}
          saving={saving}
          onApply={handleTags}
        />
      )}
    </div>
  );
}
