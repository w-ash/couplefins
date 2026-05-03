import { Info } from "lucide-react";
import type { ReactNode } from "react";
import { ResponsivePopover } from "@/components/ResponsivePopover";

export function InfoPopover({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <ResponsivePopover
      title={label}
      triggerLabel={label}
      trigger={
        <Info
          aria-hidden="true"
          className="size-3.5 text-muted-foreground hover:text-foreground"
        />
      }
      popoverClassName="absolute right-0 top-full z-50 mt-1.5 w-72 max-w-[calc(100vw-2rem)] rounded-lg border border-border bg-popover p-3 text-xs leading-relaxed text-popover-foreground shadow-lg"
    >
      {() => <div className="space-y-1.5">{children}</div>}
    </ResponsivePopover>
  );
}
