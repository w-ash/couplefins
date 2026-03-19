export type TransactionType = "personal" | "shared" | "spotted" | "household";

export function deriveTransactionType(
  household: boolean,
  payerPercentage: number,
): TransactionType {
  if (!household) return "personal";
  if (payerPercentage === 0) return "spotted";
  if (payerPercentage === 100) return "household";
  return "shared";
}

export const TYPE_LABELS: Record<TransactionType, string> = {
  personal: "Personal",
  shared: "Shared",
  spotted: "Spotted",
  household: "Household",
};

export const TYPE_OPTIONS: Array<{ value: TransactionType; label: string }> =
  Object.entries(TYPE_LABELS).map(([value, label]) => ({
    value: value as TransactionType,
    label,
  }));

const TYPE_STYLES: Record<TransactionType, string> = {
  shared: "bg-primary-muted text-primary-muted-foreground",
  spotted: "bg-warning-muted text-warning-muted-foreground",
  household: "bg-muted text-muted-foreground",
  personal: "bg-muted/50 text-muted-foreground/50",
};

export function ClassificationBadge({
  type,
  otherPersonName,
}: {
  type: TransactionType;
  otherPersonName?: string;
}) {
  const label =
    type === "spotted" && otherPersonName
      ? `Spotted for ${otherPersonName}`
      : TYPE_LABELS[type];

  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_STYLES[type]}`}
    >
      {label}
    </span>
  );
}
