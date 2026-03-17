const inputCoreClass =
  "rounded-lg border border-input bg-card px-3 text-sm text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none";

export const baseInputClass = `${inputCoreClass} py-2`;

export const selectInputClass = `${inputCoreClass} py-1.5`;

export const percentInputClass = `w-16 tabular-nums ${baseInputClass}`;

export const triggerButtonClass =
  "inline-flex items-center gap-2 rounded-lg border border-input bg-card px-3 py-1.5 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-muted";

export const actionLinkClass =
  "inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2.5 text-sm font-medium text-foreground shadow-sm transition-colors duration-150 hover:bg-muted";

export const inputErrorClass =
  "border-negative focus:border-negative focus:ring-negative";
