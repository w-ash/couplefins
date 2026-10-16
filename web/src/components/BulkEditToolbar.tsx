import { ArrowLeft, ChevronRight, Pencil } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import type { TagAction } from "@/api/generated/model";
import { Button } from "@/components/Button";
import { Combobox, type ComboboxOption } from "@/components/Combobox";
import { DepositorSelect, KEEP_DEPOSITOR } from "@/components/DepositorSelect";
import {
  OwnerSharesEditor,
  useOwnerShares,
} from "@/components/OwnerSharesEditor";
import { PercentInput } from "@/components/PercentInput";
import { SegmentedControl } from "@/components/SegmentedControl";
import { parsePercent, plural } from "@/lib/format";

export interface BulkChanges {
  payer_percentage?: number;
  category?: string;
  tags?: { action: TagAction; tags: string[] };
  /** Owner shares keyed by person id; null resets to 50/50. Joint rows only. */
  owner_shares?: Record<string, number> | null;
  /** Depositor person id; null unassigns. Joint rows only. */
  depositor_person_id?: string | null;
}

interface BulkEditToolbarProps {
  selectedIds: Set<string>;
  totalCount: number;
  selectedTagCounts: Map<string, number>;
  categoryOptions: ComboboxOption[];
  availableTags: string[];
  /** The two persons, in persons order. */
  owners: Array<{ id: string; name: string }>;
  /** True when every selected row is joint; owner-share and depositor edits need it. */
  allJoint: boolean;
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
  jointLines: string[],
): string[] {
  const lines: string[] = [...jointLines];
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
  owners,
  allJoint,
  saving,
  onApply,
  onCancel,
}: BulkEditToolbarProps) {
  const [step, setStep] = useState<"editing" | "reviewing">("editing");
  const [splitValue, setSplitValue] = useState("");
  const [category, setCategory] = useState("");
  const [tagAction, setTagAction] = useState<TagAction>("add");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  const ownerShares = useOwnerShares(owners, null);
  const [depositor, setDepositor] = useState(KEEP_DEPOSITOR);

  const count = selectedIds.size;

  const { pair: ownerPair, reset: ownerReset, firstShare } = ownerShares;
  const hasOwnerShares =
    allJoint && ownerPair !== null && (ownerReset || firstShare !== null);
  const ownerSharesHaveError = allJoint && ownerShares.invalid;
  const hasDepositor = allJoint && depositor !== KEEP_DEPOSITOR;

  // Split validation
  const splitParsed = allJoint ? null : parsePercent(splitValue);
  const hasSplit = splitParsed !== null;
  const splitHasError = !allJoint && splitValue !== "" && !hasSplit;

  // Change detection
  const hasCategory = category !== "";
  const hasTags = selectedTags.length > 0;
  const hasAnyChange =
    hasSplit || hasCategory || hasTags || hasOwnerShares || hasDepositor;
  const canReview =
    hasAnyChange && !splitHasError && !ownerSharesHaveError && count > 0;

  const jointLines: string[] = [];
  if (hasOwnerShares && ownerPair) {
    jointLines.push(
      ownerReset
        ? "Reset owner shares to 50/50"
        : `Set owner shares to ${ownerPair[0].name} ${firstShare}% / ${ownerPair[1].name} ${100 - (firstShare ?? 0)}%`,
    );
  }
  if (hasDepositor) {
    jointLines.push(
      depositor === ""
        ? "Mark deposits unassigned"
        : `Set depositor to ${owners.find((o) => o.id === depositor)?.name ?? "—"}`,
    );
  }

  const summaryLines =
    step === "reviewing"
      ? buildSummaryLines(
          splitParsed,
          category,
          categoryOptions,
          tagAction,
          selectedTags,
          jointLines,
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
    if (hasOwnerShares && ownerShares.payload !== undefined)
      changes.owner_shares = ownerShares.payload;
    if (hasDepositor) changes.depositor_person_id = depositor || null;
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
    hasOwnerShares,
    ownerShares.payload,
    hasDepositor,
    depositor,
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
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-x-6 sm:gap-y-3">
            {/* Split */}
            {!allJoint && (
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
            )}

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

            {allJoint && ownerPair && (
              <div className="sm:col-span-2">
                <OwnerSharesEditor
                  owners={ownerPair}
                  values={ownerShares.values}
                  disabled={saving}
                  isDefault={false}
                  onChange={ownerShares.onChange}
                  onReset={ownerShares.onReset}
                />
              </div>
            )}

            {allJoint && (
              <DepositorSelect
                owners={owners}
                value={depositor}
                onChange={setDepositor}
                disabled={saving}
                allowKeep
              />
            )}

            {/* Tags — full width */}
            <div className="flex items-center gap-2 text-sm text-muted-foreground sm:col-span-2">
              <span className="w-16 shrink-0">Tags</span>
              <SegmentedControl
                options={[
                  { value: "add", label: "Add" },
                  { value: "remove", label: "Remove" },
                ]}
                value={tagAction}
                onChange={switchTagAction}
                shape="pill"
              />
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
