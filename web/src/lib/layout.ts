import { cn } from "@/lib/cn";

/** Standard page padding — tighter on mobile, spacious on desktop. */
export const PAGE_PADDING = "px-4 py-6 md:px-6 md:py-12";

/** Elevated hero card — settlement status, key figures. */
export const heroCardClass =
  "rounded-xl border border-primary/20 bg-card shadow-md";

/** tr inside thead — bottom border + muted left-aligned text for column labels. */
export const tableHeaderRowClass =
  "border-b border-border text-left text-muted-foreground";

/** th/td in a compact table: every column after the first gets a left gutter. */
export const cellClass = "py-2 pl-4 first:pl-0";

/** th/td of a right-aligned money column. */
export const amountCellClass = cn(cellClass, "text-right tabular-nums");

/** A card inside a top-level card. */
export const nestedCardClass = "rounded-lg border border-border p-4";
