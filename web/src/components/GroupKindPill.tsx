import type { CategoryGroupResponseKind } from "@/api/generated/model";
import { Pill } from "@/components/Pill";

/** A group kind that is not spending, and the caption Settings shows for it. */
export type NonSpendingKind = Exclude<CategoryGroupResponseKind, "expense">;

export const NON_SPENDING_CAPTION =
  "Excluded from spending, budgets, and settlement";

const LABELS: Record<NonSpendingKind, { label: string; title: string }> = {
  transfer: {
    label: "Transfer",
    title: `Transfer — money movement, not spending. ${NON_SPENDING_CAPTION}.`,
  },
  income: {
    label: "Income",
    title: `Income — money in, not spending. ${NON_SPENDING_CAPTION}.`,
  },
};

/** Marks a transfer- or income-kind group, or one of its rows. */
export function GroupKindPill({ kind }: { kind: NonSpendingKind }) {
  const { label, title } = LABELS[kind];
  return <Pill title={title}>{label}</Pill>;
}
