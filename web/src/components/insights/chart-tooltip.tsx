import type { ReactNode } from "react";

/** The popover shell every chart tooltip uses, with an optional title line. */
export function ChartTooltipShell({
  title,
  children,
}: {
  title?: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-1.5 text-xs shadow-md">
      {title && <p className="mb-0.5 font-medium text-foreground">{title}</p>}
      {children}
    </div>
  );
}

export function ChartTooltipRow({
  label,
  value,
  swatch,
  muted,
}: {
  label: string;
  value: string;
  swatch?: string;
  muted?: boolean;
}) {
  return (
    <div className={`flex items-center gap-2 ${muted ? "opacity-60" : ""}`}>
      {swatch && (
        <span
          aria-hidden
          className="inline-block size-2 shrink-0 rounded-sm"
          style={{ background: swatch }}
        />
      )}
      <span className="text-muted-foreground">{label}</span>
      <span className="ml-auto font-medium tabular-nums text-foreground">
        {value}
      </span>
    </div>
  );
}
