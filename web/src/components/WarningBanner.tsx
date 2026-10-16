import { AlertTriangle, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** A warning box: an icon and a title line, then any detail below it. */
export function WarningBanner({
  title,
  icon: Icon = AlertTriangle,
  role,
  className,
  children,
}: {
  title: ReactNode;
  icon?: LucideIcon;
  role?: "alert" | "status";
  className?: string;
  children?: ReactNode;
}) {
  return (
    <div
      role={role}
      className={cn(
        "rounded-lg border border-warning-border bg-warning-muted p-3",
        className,
      )}
    >
      <p className="flex items-center gap-1.5 font-medium text-sm text-warning">
        <Icon className="size-4 shrink-0" aria-hidden />
        {title}
      </p>
      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}
