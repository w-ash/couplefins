import { useMemo, useState } from "react";
import { Link } from "react-router";
import { useGetCategoryGroups } from "@/api/generated/category-groups/category-groups";
import { UnmappedCategoryRow } from "@/components/UnmappedCategoryRow";
import { WarningBanner } from "@/components/WarningBanner";
import { useGroupOptions } from "@/lib/categories";

export function UnmappedCategoriesWarning({
  categories,
  className,
  compact,
}: {
  categories: string[];
  className?: string;
  /** Show a plain list with a Settings link instead of inline Combobox assignment. */
  compact?: boolean;
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
    <WarningBanner
      className={className}
      title={`${visible.length} unmapped ${visible.length === 1 ? "category" : "categories"}`}
    >
      {compact || groups.length === 0 ? (
        <ul className="list-disc pl-4 text-sm text-warning-muted-foreground">
          {visible.map((cat) => (
            <li key={cat}>{cat}</li>
          ))}
        </ul>
      ) : (
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
      )}
      {compact && (
        <Link
          to="/settings"
          className="mt-2 inline-block text-xs font-medium text-warning underline underline-offset-2"
        >
          Fix in Settings
        </Link>
      )}
    </WarningBanner>
  );
}
