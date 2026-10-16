import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** A small uppercase label beside a name: a kind, or a mark like "estimate". */
export function Pill({
  children,
  title,
  className,
}: {
  children: ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "shrink-0 rounded-full bg-muted px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-muted-foreground",
        className,
      )}
    >
      {children}
    </span>
  );
}
