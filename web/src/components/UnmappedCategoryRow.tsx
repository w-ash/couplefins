import { usePutCategoryMappings } from "@/api/generated/category-groups/category-groups";
import { Combobox, type ComboboxOption } from "@/components/Combobox";
import { useInvalidateCategories } from "@/lib/categories";

export function UnmappedCategoryRow({
  category,
  groupOptions,
  onAssigned,
  labelClassName,
}: {
  category: string;
  groupOptions: ComboboxOption[];
  onAssigned?: (category: string) => void;
  labelClassName?: string;
}) {
  const invalidate = useInvalidateCategories();
  const assignMutation = usePutCategoryMappings({
    mutation: {
      onSuccess: () => {
        invalidate();
        onAssigned?.(category);
      },
    },
  });

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
      <span
        className={`min-w-0 flex-1 truncate text-sm ${labelClassName ?? "text-foreground"}`}
      >
        {category}
      </span>
      <Combobox
        mode="single"
        options={groupOptions}
        value=""
        onChange={(groupId) =>
          assignMutation.mutate({
            data: { mappings: [{ category, group_id: groupId as string }] },
          })
        }
        disabled={assignMutation.isPending}
        allowCreate={false}
        placeholder="Assign to group..."
        className="w-full sm:w-48"
      />
    </div>
  );
}
