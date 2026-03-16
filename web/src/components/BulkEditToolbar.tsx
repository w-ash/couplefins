import { ArrowLeft, ChevronRight, Pencil } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Button } from "@/components/Button";
import { Combobox, type ComboboxOption } from "@/components/Combobox";
import { PercentInput } from "@/components/PercentInput";
import { parsePercent, plural } from "@/lib/format";
import type { TagAction } from "@/lib/transactions";

export interface BulkChanges {
  payer_percentage?: number;
  category?: string;
  tags?: { action: TagAction; tags: string[] };
}

interface BulkEditToolbarProps {
  selectedIds: Set<string>;
  totalCount: number;
  selectedTagCounts: Map<string, number>;
  categoryOptions: ComboboxOption[];
  availableTags: string[];
  saving: boolean;
  onApply: (ids: string[], changes: BulkChanges) => void;
  onCancel: () => void;
}

function buildSummaryLines(
  splitParsed: number | null,
  category: string,
  categoryOptions: ComboboxOption[],
  tagAction: TagAction,
  selectedTags: string[],
): string[] {
  const lines: string[] = [];
  if (splitParsed !== null) {
    lines.push(`Set split to ${splitParsed}%`);
  }
  if (category) {
    const label =
      categoryOptions.find((o) => o.value === category)?.label ?? category;
    lines.push(`Change category to ${label}`);
  }
  if (selectedTags.length > 0) {
    const verb = tagAction === "add" ? "Add" : "Remove";
    lines.push(`${verb} tags: ${selectedTags.join(", ")}`);
  }
  return lines;
}

export function BulkEditToolbar({
  selectedIds,
  totalCount,
  selectedTagCounts,
  categoryOptions,
  availableTags,
  saving,
  onApply,
  onCancel,
}: BulkEditToolbarProps) {
  const [step, setStep] = useState<"editing" | "reviewing">("editing");
  const [splitValue, setSplitValue] = useState("");
  const [category, setCategory] = useState("");
  const [tagAction, setTagAction] = useState<TagAction>("add");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  const count = selectedIds.size;

  // Split validation
  const splitParsed = parsePercent(splitValue);
  const hasSplit = splitParsed !== null;
  const splitHasError = splitValue !== "" && !hasSplit;

  // Change detection
  const hasCategory = category !== "";
  const hasTags = selectedTags.length > 0;
  const hasAnyChange = hasSplit || hasCategory || hasTags;
  const canReview = hasAnyChange && !splitHasError && count > 0;

  const summaryLines =
    step === "reviewing"
      ? buildSummaryLines(
          splitParsed,
          category,
          categoryOptions,
          tagAction,
          selectedTags,
        )
      : [];

  const switchTagAction = useCallback(
    (newAction: TagAction) => {
      if (newAction !== tagAction) {
        setTagAction(newAction);
        setSelectedTags([]);
      }
    },
    [tagAction],
  );

  const tagOptions: ComboboxOption[] = useMemo(() => {
    if (tagAction === "remove") {
      return [...selectedTagCounts.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([tag, tagCount]) => ({
          value: tag,
          label: tagCount < count ? `${tag} (${tagCount}/${count})` : tag,
        }));
    }
    return availableTags.map((tag) => {
      const tagCount = selectedTagCounts.get(tag) ?? 0;
      if (tagCount > 0 && tagCount < count) {
        return {
          value: tag,
          label: `${tag} — on ${tagCount} of ${count}`,
        };
      }
      if (tagCount === count) {
        return { value: tag, label: `${tag} (all)` };
      }
      return { value: tag, label: tag };
    });
  }, [tagAction, availableTags, selectedTagCounts, count]);

  const handleApply = useCallback(() => {
    const changes: BulkChanges = {};
    if (splitParsed !== null) changes.payer_percentage = splitParsed;
    if (hasCategory) changes.category = category;
    if (hasTags) changes.tags = { action: tagAction, tags: selectedTags };
    onApply([...selectedIds], changes);
  }, [
    splitParsed,
    hasCategory,
    category,
    hasTags,
    tagAction,
    selectedTags,
    selectedIds,
    onApply,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        if (step === "editing" && canReview) setStep("reviewing");
        else if (step === "reviewing") handleApply();
      } else if (e.key === "Escape") {
        if (step === "reviewing") setStep("editing");
        else onCancel();
      }
    },
    [step, canReview, handleApply, onCancel],
  );

  const label = plural("transaction", count);

  return (
    <div
      role="toolbar"
      aria-label="Bulk edit"
      className="space-y-3 rounded-lg border border-border bg-card px-4 py-3 shadow-sm"
      onKeyDown={handleKeyDown}
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <Pencil className="size-3.5 text-primary" />
          {count} of {totalCount} selected
        </span>
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

      {step === "editing" ? (
        <>
          {/* Form fields */}
          <div className="grid grid-cols-2 gap-x-6 gap-y-3">
            {/* Split */}
            <label
              htmlFor="bulk-split"
              className="flex items-center gap-2 text-sm text-muted-foreground"
            >
              <span className="w-16 shrink-0">Split</span>
              <PercentInput
                id="bulk-split"
                value={splitValue}
                onChange={setSplitValue}
                placeholder="—"
                disabled={saving}
                error={splitHasError}
              />
            </label>

            {/* Category */}
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="w-16 shrink-0">Category</span>
              <Combobox
                mode="single"
                options={categoryOptions}
                value={category}
                onChange={(v) => setCategory(v as string)}
                placeholder="No change"
                disabled={saving}
                allowCreate={false}
                className="flex-1"
              />
            </div>

            {/* Tags — full width */}
            <div className="col-span-2 flex items-center gap-2 text-sm text-muted-foreground">
              <span className="w-16 shrink-0">Tags</span>
              <div className="flex shrink-0 rounded-full border border-border bg-muted/50 p-0.5">
                <button
                  type="button"
                  onClick={() => switchTagAction("add")}
                  className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                    tagAction === "add"
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground"
                  }`}
                >
                  Add
                </button>
                <button
                  type="button"
                  onClick={() => switchTagAction("remove")}
                  className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                    tagAction === "remove"
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
                placeholder="No change"
                disabled={saving}
                allowCreate={tagAction === "add"}
                className="flex-1"
              />
            </div>
          </div>

          {/* Review button */}
          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={() => setStep("reviewing")}
              disabled={!canReview || saving}
              icon={<ChevronRight className="size-3.5" />}
            >
              Review Changes
            </Button>
          </div>
        </>
      ) : (
        <>
          {/* Review summary */}
          <div aria-live="polite">
            <p className="mb-2 text-sm font-medium text-foreground">
              Apply to {label}:
            </p>
            <ul className="space-y-1">
              {summaryLines.map((line) => (
                <li
                  key={line}
                  className="flex items-start gap-2 text-sm text-foreground"
                >
                  <span className="mt-0.5 text-primary">&#x2022;</span>
                  {line}
                </li>
              ))}
            </ul>
          </div>

          {/* Review actions */}
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setStep("editing")}
              disabled={saving}
              icon={<ArrowLeft className="size-3.5" />}
            >
              Back
            </Button>
            <Button
              size="sm"
              onClick={handleApply}
              disabled={saving}
              loading={saving}
              loadingText="Applying"
            >
              Apply Changes
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
