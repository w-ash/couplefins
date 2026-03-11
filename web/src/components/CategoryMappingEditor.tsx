import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  Upload,
} from "lucide-react";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import {
  bulkUpdateMappings,
  CATEGORY_GROUPS_QUERY_KEY,
  type CategoryGroup,
  createCategoryGroup,
  deleteCategoryGroup,
  fetchCategoryGroups,
  fetchUnmappedCategories,
  renameCategoryGroup,
  UNMAPPED_CATEGORIES_QUERY_KEY,
  useInvalidateCategories,
} from "@/lib/categories";

// -- Unmapped category row --

function UnmappedRow({
  category,
  groups,
}: {
  category: string;
  groups: CategoryGroup[];
}) {
  const invalidate = useInvalidateCategories();
  const assignMutation = useMutation({
    mutationFn: (groupId: string) =>
      bulkUpdateMappings([{ category, group_id: groupId }]),
    onSuccess: invalidate,
  });

  return (
    <div className="flex items-center gap-3">
      <span className="min-w-0 flex-1 truncate text-sm text-foreground">
        {category}
      </span>
      <select
        aria-label={`Assign ${category} to group`}
        value=""
        onChange={(e) => assignMutation.mutate(e.target.value)}
        disabled={assignMutation.isPending}
        className="w-48 rounded-lg border border-input bg-card px-2.5 py-1.5 text-sm text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none disabled:opacity-50"
      >
        <option value="" disabled>
          Assign to group...
        </option>
        {groups.map((g) => (
          <option key={g.id} value={g.id}>
            {g.name}
          </option>
        ))}
      </select>
    </div>
  );
}

// -- Group card --

function GroupCard({ group }: { group: CategoryGroup }) {
  const invalidate = useInvalidateCategories();
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(group.name);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (confirmDelete && !dialog.open) dialog.showModal();
    else if (!confirmDelete && dialog.open) dialog.close();
  }, [confirmDelete]);

  const renameMutation = useMutation({
    mutationFn: (name: string) => renameCategoryGroup(group.id, name),
    onSuccess: () => {
      setEditing(false);
      invalidate();
    },
  });

  const deleteGroupMutation = useMutation({
    mutationFn: () => deleteCategoryGroup(group.id),
    onSuccess: () => {
      setConfirmDelete(false);
      invalidate();
    },
  });

  function handleSaveRename() {
    const trimmed = editName.trim();
    if (trimmed && trimmed !== group.name) {
      renameMutation.mutate(trimmed);
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

  return (
    <>
      <div className="rounded-xl border border-border bg-card shadow-sm">
        <div className="flex items-center gap-3 p-4">
          {editing ? (
            <input
              ref={inputRef}
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onBlur={handleSaveRename}
              onKeyDown={handleRenameKeyDown}
              aria-label="Group name"
              className="min-w-0 flex-1 rounded-lg border border-input bg-card px-2.5 py-1 text-sm font-medium text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none"
            />
          ) : (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="flex min-w-0 flex-1 items-center gap-2 text-left"
            >
              <ChevronDown
                className={`size-4 shrink-0 text-muted-foreground transition-transform duration-200 ${expanded ? "" : "-rotate-90"}`}
              />
              <span className="truncate font-medium text-sm text-foreground">
                {group.name}
              </span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {group.categories.length}
              </span>
            </button>
          )}

          <button
            type="button"
            onClick={startEditing}
            aria-label={`Rename ${group.name}`}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground"
          >
            <Pencil className="size-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            aria-label={`Delete ${group.name}`}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-destructive"
          >
            <Trash2 className="size-3.5" />
          </button>
        </div>

        {/* Expanded category list */}
        <div
          className="grid transition-[grid-template-rows] duration-200"
          style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
        >
          <div className="overflow-hidden">
            {group.categories.length > 0 ? (
              <ul className="border-t border-border-muted px-4 py-3">
                {group.categories.map((cat) => (
                  <li key={cat} className="py-1 text-sm text-muted-foreground">
                    {cat}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="border-t border-border-muted px-4 py-3 text-sm text-muted-foreground">
                No categories assigned yet.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      <dialog
        ref={dialogRef}
        aria-labelledby={`delete-${group.id}-title`}
        onClose={() => setConfirmDelete(false)}
        className="mx-4 w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-lg backdrop:bg-black/40"
      >
        <h3
          id={`delete-${group.id}-title`}
          className="font-medium text-foreground"
        >
          Remove &ldquo;{group.name}&rdquo;?
        </h3>
        <p className="mt-2 text-sm text-muted-foreground">
          {group.categories.length > 0
            ? `${group.categories.length} ${group.categories.length === 1 ? "category" : "categories"} will become unmapped.`
            : "This group has no categories."}
        </p>
        <div className="mt-5 flex gap-3">
          <button
            type="button"
            onClick={() => setConfirmDelete(false)}
            className="flex-1 rounded-lg border border-input bg-card px-4 py-2 text-sm font-medium text-secondary-foreground shadow-sm transition-colors hover:bg-muted"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => deleteGroupMutation.mutate()}
            disabled={deleteGroupMutation.isPending}
            className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-destructive px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-destructive/90 disabled:opacity-50"
          >
            {deleteGroupMutation.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : null}
            Remove Group
          </button>
        </div>
      </dialog>
    </>
  );
}

// -- Add group input --

function AddGroupForm() {
  const invalidate = useInvalidateCategories();
  const [name, setName] = useState("");

  const createMutation = useMutation({
    mutationFn: createCategoryGroup,
    onSuccess: () => {
      setName("");
      invalidate();
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (trimmed) createMutation.mutate(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="New group name..."
        aria-label="New group name"
        className="min-w-0 flex-1 rounded-lg border border-input bg-card px-3 py-2 text-sm text-foreground shadow-sm placeholder:text-placeholder focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none"
      />
      <button
        type="submit"
        disabled={!name.trim() || createMutation.isPending}
        className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {createMutation.isPending ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Plus className="size-4" />
        )}
        Add Group
      </button>
    </form>
  );
}

// -- Main editor --

export function CategoryMappingEditor() {
  const groupsQuery = useQuery({
    queryKey: [...CATEGORY_GROUPS_QUERY_KEY],
    queryFn: fetchCategoryGroups,
  });

  const unmappedQuery = useQuery({
    queryKey: [...UNMAPPED_CATEGORIES_QUERY_KEY],
    queryFn: fetchUnmappedCategories,
  });

  // Loading
  if (groupsQuery.isLoading || unmappedQuery.isLoading) {
    return (
      <output className="block space-y-3" aria-label="Loading categories">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-14 animate-pulse rounded-xl border border-border bg-muted"
          />
        ))}
      </output>
    );
  }

  // Error
  if (groupsQuery.isError || unmappedQuery.isError) {
    return (
      <div className="rounded-lg border border-destructive-border bg-destructive-muted p-4 text-sm text-destructive-muted-foreground">
        <p>Failed to load categories.</p>
        <button
          type="button"
          onClick={() => {
            groupsQuery.refetch();
            unmappedQuery.refetch();
          }}
          className="mt-2 font-medium text-destructive underline underline-offset-2"
        >
          Retry
        </button>
      </div>
    );
  }

  const groups = groupsQuery.data ?? [];
  const unmapped = unmappedQuery.data ?? [];

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
        <div className="rounded-xl border border-warning-border bg-warning-muted p-4">
          <p className="mb-3 flex items-center gap-1.5 font-medium text-sm text-warning">
            <AlertTriangle className="size-4 shrink-0" />
            {unmapped.length} unmapped{" "}
            {unmapped.length === 1 ? "category" : "categories"}
          </p>
          <div className="space-y-2">
            {unmapped.map((cat) => (
              <UnmappedRow key={cat} category={cat} groups={groups} />
            ))}
          </div>
        </div>
      )}

      {/* Groups */}
      <div className="space-y-2">
        {groups.map((group) => (
          <GroupCard key={group.id} group={group} />
        ))}
      </div>

      <AddGroupForm />
    </div>
  );
}
