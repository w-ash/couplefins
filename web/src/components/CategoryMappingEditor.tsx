import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  Pencil,
  Plus,
  Trash2,
  Upload,
} from "lucide-react";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Button } from "@/components/Button";
import { PageError, PageLoading } from "@/components/PageStates";
import {
  bulkUpdateMappings,
  CATEGORY_GROUPS_QUERY_KEY,
  type CategoryGroup,
  createCategoryGroup,
  deleteCategoryGroup,
  fetchCategoryGroups,
  fetchUnmappedCategories,
  UNMAPPED_CATEGORIES_QUERY_KEY,
  updateCategoryGroup,
  useInvalidateCategories,
} from "@/lib/categories";
import { getCategoryGroupIcon, ICON_OPTIONS } from "@/lib/category-icons";

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

function IconPicker({
  currentIcon,
  onSelect,
}: {
  currentIcon: string | null;
  onSelect: (icon: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node))
        setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const CurrentIcon = getCategoryGroupIcon(currentIcon);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen(!open);
        }}
        aria-label="Change icon"
        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-foreground"
      >
        <CurrentIcon className="size-4" />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-10 mt-1 grid grid-cols-5 gap-1 rounded-lg border border-border bg-card p-2 shadow-lg">
          {ICON_OPTIONS.map(({ name, Icon }) => (
            <button
              key={name}
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSelect(name);
                setOpen(false);
              }}
              className={`rounded-md p-1.5 transition-colors ${
                name === currentIcon
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
              aria-label={name}
            >
              <Icon className="size-4" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

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

  const updateMutation = useMutation({
    mutationFn: (fields: { name?: string; icon?: string | null }) =>
      updateCategoryGroup(group.id, {
        name: fields.name ?? group.name,
        icon: "icon" in fields ? fields.icon : group.icon,
      }),
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
      updateMutation.mutate({ name: trimmed });
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

  const GroupIcon = getCategoryGroupIcon(group.icon);

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
              <GroupIcon className="size-4 shrink-0 text-muted-foreground" />
              <span className="truncate font-medium text-sm text-foreground">
                {group.name}
              </span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {group.categories.length}
              </span>
            </button>
          )}

          <IconPicker
            currentIcon={group.icon}
            onSelect={(icon) =>
              updateMutation.mutate({ name: group.name, icon })
            }
          />
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
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setConfirmDelete(false)}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => deleteGroupMutation.mutate()}
            loading={deleteGroupMutation.isPending}
            className="flex-1"
          >
            Remove Group
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
    return <PageLoading label="Loading categories..." />;
  }

  // Error
  if (groupsQuery.isError || unmappedQuery.isError) {
    return (
      <PageError
        error={new Error("Failed to load categories.")}
        onRetry={() => {
          groupsQuery.refetch();
          unmappedQuery.refetch();
        }}
      />
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
