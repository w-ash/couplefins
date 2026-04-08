import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

export function ExpandChevron({
  expanded,
  className,
}: {
  expanded: boolean;
  className?: string;
}) {
  return (
    <ChevronDown
      className={cn(
        "size-4 shrink-0 text-muted-foreground transition-transform duration-200",
        !expanded && "-rotate-90",
        className,
      )}
    />
  );
}
