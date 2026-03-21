import { AlertTriangle } from "lucide-react";
import { useMemo, useState } from "react";
import { useGetCategoryGroups } from "@/api/generated/category-groups/category-groups";
import { UnmappedCategoryRow } from "@/components/UnmappedCategoryRow";
import { useGroupOptions } from "@/lib/categories";

export function UnmappedCategoriesWarning({
  categories,
  className,
}: {
  categories: string[];
  className?: string;
}) {
  const { data: groupsResponse } = useGetCategoryGroups();
  const groups = groupsResponse?.data ?? [];
  const groupOptions = useGroupOptions(groups);

  // Track locally assigned categories so they disappear immediately
  const [assigned, setAssigned] = useState<Set<string>>(new Set());

  const visible = useMemo(
    () => categories.filter((cat) => !assigned.has(cat)),
    [categories, assigned],
  );

  if (visible.length === 0) return null;

  return (
    <div
      className={`rounded-lg border border-warning-border bg-warning-muted p-3 ${className ?? ""}`}
    >
      <p className="mb-2 flex items-center gap-1.5 font-medium text-sm text-warning">
        <AlertTriangle className="size-4 shrink-0" />
        {visible.length} unmapped{" "}
        {visible.length === 1 ? "category" : "categories"}
      </p>
      {groups.length > 0 ? (
        <div className="space-y-2">
          {visible.map((cat) => (
            <UnmappedCategoryRow
              key={cat}
              category={cat}
              groupOptions={groupOptions}
              onAssigned={(c) => setAssigned((prev) => new Set([...prev, c]))}
              labelClassName="text-warning-muted-foreground"
            />
          ))}
        </div>
      ) : (
        <ul className="text-sm text-warning-muted-foreground">
          {visible.map((cat) => (
            <li key={cat}>{cat}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
