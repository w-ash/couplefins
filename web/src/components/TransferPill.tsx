export const TRANSFER_CAPTION =
  "Excluded from spending, budgets, and settlement";

const TITLE = `Transfer — money movement, not spending. ${TRANSFER_CAPTION}.`;

/** Marks a transfer-kind group or one of its rows: money movement, not spending. */
export function TransferPill() {
  return (
    <span
      className="shrink-0 rounded-full bg-muted px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-muted-foreground"
      title={TITLE}
    >
      Transfer
    </span>
  );
}
