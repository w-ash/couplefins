import { Clock, Upload } from "lucide-react";
import type { TransactionEditResponse } from "@/api/generated/model";
import { useGetTransactionEdits } from "@/api/generated/transactions/transactions";
import { formatCurrency, formatDate, formatDateTime } from "@/lib/format";

interface TransactionEditHistoryProps {
  transactionId: string;
  personNames: Map<string, string>;
}

const fieldLabels: Record<string, string> = {
  date: "Date",
  amount: "Amount",
  category: "Category",
  notes: "Notes",
  tags: "Tags",
  payer_percentage: "Split",
  household: "Type",
  is_excluded: "Excluded",
};

function formatEditValue(fieldName: string, value: string): string {
  if (fieldName === "payer_percentage") return value ? `${value}%` : "—";
  if (fieldName === "household")
    return value === "true" ? "Household" : "Personal";
  if (fieldName === "is_excluded") return value === "true" ? "Yes" : "No";
  if (fieldName === "date" && value) return formatDate(value);
  if (fieldName === "amount" && value) return formatCurrency(Number(value));
  return value || "—";
}

export function TransactionEditHistory({
  transactionId,
  personNames,
}: TransactionEditHistoryProps) {
  const { data: response, isLoading } = useGetTransactionEdits(transactionId, {
    query: { staleTime: 30_000 },
  });

  const data = response?.status === 200 ? response.data : undefined;
  const importEvent = data?.import_event ?? null;
  const edits = data?.edits ?? [];

  if (isLoading) return null;
  if (!importEvent && edits.length === 0) return null;

  const resolveName = (id: string | null) =>
    id ? (personNames.get(id) ?? "Unknown") : null;

  return (
    <div className="mt-3 border-t border-border-muted pt-3">
      <p className="mb-2 flex items-center gap-1 text-sm font-medium text-muted-foreground">
        <Clock className="size-3" />
        History
      </p>
      <ol
        aria-label="Edit history"
        className="relative ml-1.5 border-l-2 border-border-muted"
      >
        {edits.map((edit: TransactionEditResponse) => {
          const name = resolveName(edit.edited_by_person_id);
          return (
            <li key={edit.id} className="relative ml-4 pb-2.5">
              <span className="absolute -left-[calc(0.5rem+1px)] top-1.5 size-1.5 rounded-full bg-muted-foreground/40" />
              <p className="text-xs text-muted-foreground">
                <span className="tabular-nums">
                  {formatDateTime(edit.edited_at)}
                </span>
                {" · "}
                {name ? <span className="text-foreground">{name}</span> : null}
                {name ? " changed " : "Changed "}
                <span className="text-foreground">
                  {fieldLabels[edit.field_name] ?? edit.field_name}
                </span>
                {": "}
                {formatEditValue(edit.field_name, edit.old_value)}
                {" → "}
                {formatEditValue(edit.field_name, edit.new_value)}
              </p>
            </li>
          );
        })}
        {importEvent && (
          <li className="relative ml-4 pb-1">
            <span className="absolute -left-[calc(0.5rem+1px)] top-1.5 size-1.5 rounded-full bg-muted-foreground/40" />
            <p className="text-xs text-muted-foreground">
              <Upload className="mr-0.5 -mt-0.5 inline size-3" />
              Imported by{" "}
              <span className="text-foreground">
                {resolveName(importEvent.person_id) ?? "Unknown"}
              </span>{" "}
              on{" "}
              <span className="tabular-nums">
                {formatDateTime(importEvent.imported_at)}
              </span>
            </p>
          </li>
        )}
      </ol>
    </div>
  );
}
