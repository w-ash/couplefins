import { Plus, Upload } from "lucide-react";
import { type KeyboardEvent, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { useGetBudgets } from "@/api/generated/budgets/budgets";
import {
  useDeleteCategoryGroup,
  useGetCategoryGroups,
  useGetUnmappedCategories,
  usePostCategoryGroup,
  usePutCategoryGroup,
} from "@/api/generated/category-groups/category-groups";
import type { CategoryGroupResponse } from "@/api/generated/model";
import { BottomSheet } from "@/components/BottomSheet";
import { Button } from "@/components/Button";
import { Combobox } from "@/components/Combobox";
import { ExpandChevron } from "@/components/ExpandChevron";
import { PageError, PageLoading } from "@/components/PageStates";
import { UnmappedCategoriesWarning } from "@/components/UnmappedCategoriesWarning";
import { useDialogSync } from "@/hooks/useDialogSync";
import { useGroupOptions, useInvalidateCategories } from "@/lib/categories";
import { getCategoryGroupIcon, ICON_OPTIONS } from "@/lib/category-icons";
import { baseInputClass } from "@/lib/input-styles";

// -- Icon picker sheet --

function IconPickerSheet({
  open,
  onClose,
  currentIcon,
  onSelect,
}: {
  open: boolean;
  onClose: () => void;
  currentIcon: string | null;
  onSelect: (icon: string) => void;
}) {
  return (
    <BottomSheet open={open} onClose={onClose}>
      <p className="mb-3 text-sm font-medium text-foreground">Choose an icon</p>
      <div className="grid grid-cols-5 gap-1 pb-2">
        {ICON_OPTIONS.map(({ name, Icon }) => (
          <button
            key={name}
            type="button"
            onClick={() => {
              onSelect(name);
              onClose();
            }}
            className={`rounded-md p-2.5 transition-colors ${
              name === currentIcon
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
            aria-label={name}
          >
            <Icon className="mx-auto size-5" />
          </button>
        ))}
      </div>
    </BottomSheet>
  );
}

// -- Group card --

function GroupCard({
  group,
  allGroups,
}: {
  group: CategoryGroupResponse;
  allGroups: CategoryGroupResponse[];
}) {
  const invalidate = useInvalidateCategories();
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(group.name);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [iconPickerOpen, setIconPickerOpen] = useState(false);
  const [moveToGroupId, setMoveToGroupId] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useDialogSync(confirmDelete);

  // Lazy-fetch budgets only when delete dialog is open
  const { data: budgetsResponse } = useGetBudgets({
    query: { enabled: confirmDelete },
  });
  const groupBudgets = useMemo(
    () => (budgetsResponse?.data ?? []).filter((b) => b.group_id === group.id),
    [budgetsResponse, group.id],
  );

  // Combobox options: all groups except this one
  const otherGroups = useMemo(
    () => allGroups.filter((g) => g.id !== group.id),
    [allGroups, group.id],
  );
  const moveOptions = useGroupOptions(otherGroups);

  const updateMutation = usePutCategoryGroup({
    mutation: {
      onSuccess: () => {
        setEditing(false);
        invalidate();
      },
    },
  });

  const deleteGroupMutation = useDeleteCategoryGroup({
    mutation: {
      onSuccess: () => {
        setConfirmDelete(false);
        setMoveToGroupId("");
        invalidate();
      },
    },
  });

  const hasCategories = group.categories.length > 0;
  const hasBudgets = groupBudgets.length > 0;
  const latestBudget = hasBudgets
    ? groupBudgets.reduce((latest, b) =>
        b.year > latest.year ||
        (b.year === latest.year && b.month > latest.month)
          ? b
          : latest,
      )
    : null;

  function handleSaveRename() {
    const trimmed = editName.trim();
    if (trimmed && trimmed !== group.name) {
      updateMutation.mutate({
        groupId: group.id,
        data: { name: trimmed, icon: group.icon },
      });
    } else {
      setEditing(false);
      setEditName(group.name);
    }
  }

  function handleRenameKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") handleSaveRename();
    if (e.key === "Escape") {
      setEditing(false);
      setEditName(group.name);
    }
  }

  function startEditing() {
    setEditing(true);
    setEditName(group.name);
    requestAnimationFrame(() => inputRef.current?.select());
  }

  function cancelEditing() {
    setEditing(false);
    setEditName(group.name);
  }

  function handleCancelDelete() {
    setConfirmDelete(false);
    setMoveToGroupId("");
  }

  function handleConfirmDelete() {
    deleteGroupMutation.mutate({
      groupId: group.id,
      params: moveToGroupId ? { move_categories_to: moveToGroupId } : undefined,
    });
  }

  const GroupIcon = getCategoryGroupIcon(group.icon);

  return (
    <>
      <div className="rounded-xl border border-border bg-card shadow-sm">
        {/* Primary row — clean, read-only (or rename input) */}
        <div className="flex items-center gap-3 p-4">
          {editing ? (
            <>
              <ExpandChevron expanded={expanded} />
              <input
                ref={inputRef}
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onBlur={handleSaveRename}
                onKeyDown={handleRenameKeyDown}
                onClick={(e) => e.stopPropagation()}
                aria-label="Group name"
                className="min-w-0 flex-1 rounded-lg border border-input bg-card px-2.5 py-1 text-sm font-medium text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none"
              />
              <span className="text-xs text-muted-foreground tabular-nums">
                {group.categories.length}
              </span>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="flex min-w-0 flex-1 items-center gap-2 text-left"
            >
              <ExpandChevron expanded={expanded} />
              <GroupIcon className="size-4 shrink-0 text-muted-foreground" />
              <span className="truncate font-medium text-sm text-foreground">
                {group.name}
              </span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {group.categories.length}
              </span>
            </button>
          )}
        </div>

        {/* Expanded: category list + action bar */}
        <div
          className="grid transition-[grid-template-rows] duration-200"
          style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
        >
          <div className="overflow-hidden">
            {/* Category list */}
            {group.categories.length > 0 ? (
              <ul className="border-t border-border-muted px-4 py-3">
                {group.categories.map((cat) => (
                  <li key={cat.name} className="py-1">
                    <span className="text-sm text-muted-foreground">
                      {cat.name}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="border-t border-border-muted px-4 py-3 text-sm text-muted-foreground">
                No categories assigned yet.
              </p>
            )}

            {/* Action bar */}
            <div className="flex items-center gap-4 border-t border-border-muted px-4 py-3">
              {editing ? (
                <>
                  <button
                    type="button"
                    onClick={handleSaveRename}
                    className="text-sm font-medium text-primary transition-colors hover:text-primary/80"
                  >
                    Save
                  </button>
                  <button
                    type="button"
                    onClick={cancelEditing}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => setIconPickerOpen(true)}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    Change Icon
                  </button>
                  <button
                    type="button"
                    onClick={startEditing}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(true)}
                    className="text-sm text-destructive transition-colors hover:text-destructive/80"
                  >
                    Delete Group
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Icon picker bottom sheet */}
      <IconPickerSheet
        open={iconPickerOpen}
        onClose={() => setIconPickerOpen(false)}
        currentIcon={group.icon}
        onSelect={(icon) =>
          updateMutation.mutate({
            groupId: group.id,
            data: { name: group.name, icon },
          })
        }
      />

      {/* Delete confirmation dialog */}
      <dialog
        ref={dialogRef}
        aria-labelledby={`delete-${group.id}-title`}
        onClose={handleCancelDelete}
        className="mx-4 w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-lg backdrop:bg-black/40"
      >
        <h3
          id={`delete-${group.id}-title`}
          className="font-medium text-foreground"
        >
          Remove &ldquo;{group.name}&rdquo;?
        </h3>
        <div className="mt-2 space-y-1 text-sm text-muted-foreground">
          {hasCategories && (
            <p>
              {group.categories.length}{" "}
              {group.categories.length === 1 ? "category" : "categories"} will
              need a new home.
            </p>
          )}
          {hasBudgets && latestBudget && (
            <p>
              The ${latestBudget.monthly_amount.toLocaleString()}/mo budget will
              also be removed.
            </p>
          )}
          {!hasCategories && !hasBudgets && <p>This group is empty.</p>}
        </div>

        {hasCategories && (
          <div className="mt-3">
            <label
              htmlFor={`move-${group.id}`}
              className="mb-1 block text-sm font-medium text-foreground"
            >
              Move to
            </label>
            <Combobox
              mode="single"
              options={moveOptions}
              value={moveToGroupId}
              onChange={(v) => setMoveToGroupId(v as string)}
              placeholder="Select a group..."
              allowCreate={false}
            />
          </div>
        )}

        <div className="mt-5 flex gap-3">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleCancelDelete}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={handleConfirmDelete}
            disabled={hasCategories && !moveToGroupId}
            loading={deleteGroupMutation.isPending}
            className="flex-1"
          >
            {hasCategories ? "Move & Remove" : "Remove Group"}
          </Button>
        </div>
      </dialog>
    </>
  );
}

// -- Add group input --

function AddGroupForm() {
  const invalidate = useInvalidateCategories();
  const [name, setName] = useState("");

  const createMutation = usePostCategoryGroup({
    mutation: {
      onSuccess: () => {
        setName("");
        invalidate();
      },
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (trimmed) createMutation.mutate({ data: { name: trimmed } });
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="New group name..."
        aria-label="New group name"
        className={`min-w-0 flex-1 ${baseInputClass}`}
      />
      <Button
        type="submit"
        size="sm"
        disabled={!name.trim()}
        loading={createMutation.isPending}
        icon={<Plus className="size-4" />}
      >
        Add Group
      </Button>
    </form>
  );
}

// -- Main editor --

export function CategoryMappingEditor() {
  const {
    data: groupsResponse,
    isLoading: groupsLoading,
    isError: groupsError,
    refetch: refetchGroups,
  } = useGetCategoryGroups();
  const groups = groupsResponse?.data ?? [];

  const {
    data: unmappedResponse,
    isLoading: unmappedLoading,
    isError: unmappedError,
    refetch: refetchUnmapped,
  } = useGetUnmappedCategories();
  const unmapped = unmappedResponse?.data ?? [];
  // Loading
  if (groupsLoading || unmappedLoading) {
    return <PageLoading label="Loading categories..." />;
  }

  // Error
  if (groupsError || unmappedError) {
    return (
      <PageError
        error={new Error("Failed to load categories.")}
        onRetry={() => {
          refetchGroups();
          refetchUnmapped();
        }}
      />
    );
  }

  // Empty — no groups and no unmapped
  if (groups.length === 0 && unmapped.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          <Upload className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No categories yet.{" "}
            <Link
              to="/upload"
              className="font-medium text-primary underline-offset-2 hover:underline"
            >
              Upload a CSV
            </Link>{" "}
            to get started.
          </p>
        </div>
        <AddGroupForm />
      </div>
    );
  }

  // Data state
  return (
    <div className="space-y-4">
      {/* Unmapped banner */}
      {unmapped.length > 0 && (
        <UnmappedCategoriesWarning categories={unmapped} />
      )}

      {/* Groups */}
      <div className="space-y-2">
        {groups.map((group) => (
          <GroupCard key={group.id} group={group} allGroups={groups} />
        ))}
      </div>

      <AddGroupForm />
    </div>
  );
}
