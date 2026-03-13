import { AlertTriangle } from "lucide-react";
import { Link } from "react-router";

export function UnmappedCategoriesWarning({
  categories,
  className,
}: {
  categories: string[];
  className?: string;
}) {
  if (categories.length === 0) return null;
  return (
    <div
      className={`rounded-lg border border-warning-border bg-warning-muted p-3 ${className ?? ""}`}
    >
      <p className="mb-1 flex items-center gap-1.5 font-medium text-sm text-warning">
        <AlertTriangle className="size-4 shrink-0" />
        Unmapped categories
      </p>
      <ul className="text-sm text-warning-muted-foreground">
        {categories.map((cat) => (
          <li key={cat}>{cat}</li>
        ))}
      </ul>
      <Link
        to="/settings"
        className="mt-2 inline-block text-sm font-medium text-warning hover:underline"
      >
        Map these in Settings →
      </Link>
    </div>
  );
}
