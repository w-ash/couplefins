import { ChevronDown } from "lucide-react";

export function ExpandChevron({
  expanded,
  className,
}: {
  expanded: boolean;
  className?: string;
}) {
  return (
    <ChevronDown
      className={`size-4 shrink-0 text-muted-foreground transition-transform duration-200 ${expanded ? "" : "-rotate-90"} ${className ?? ""}`}
    />
  );
}
