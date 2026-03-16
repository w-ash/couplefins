import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/Button";
import type { ComboboxOption } from "@/components/Combobox";
import { Combobox } from "@/components/Combobox";
import { computeShares, formatCurrency, formatDate } from "@/lib/format";
import type { ReconciliationTransaction } from "@/lib/reconciliation";
import type {
  TransactionEdit,
  TransactionUpdateFields,
} from "@/lib/transactions";
import { fetchTransactionEdits } from "@/lib/transactions";

interface TransactionEditorProps {
  tx: ReconciliationTransaction;
  payerName: string;
  otherName: string;
  categoryOptions: ComboboxOption[];
  tagOptions: ComboboxOption[];
  saving?: boolean;
  onSave: (fields: TransactionUpdateFields) => void;
  onCancel: () => void;
}

const editDateFmt = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

const fieldLabels: Record<string, string> = {
  date: "Date",
  amount: "Amount",
  category: "Category",
  tags: "Tags",
  payer_percentage: "Split",
};

function formatEditValue(fieldName: string, value: string): string {
  if (fieldName === "payer_percentage") return value ? `${value}%` : "—";
  if (fieldName === "date" && value) return formatDate(value);
  if (fieldName === "amount" && value) return formatCurrency(Number(value));
  return value || "—";
}

function EditHistory({ transactionId }: { transactionId: string }) {
  const { data } = useQuery({
    queryKey: ["transaction-edits", transactionId],
    queryFn: () => fetchTransactionEdits(transactionId),
  });

  const edits = data?.edits ?? [];
  if (edits.length === 0) return null;

  return (
    <div className="mt-3 border-t border-border-muted pt-3">
      <p className="mb-1.5 text-xs font-medium text-muted-foreground">
        Edit History
      </p>
      <div className="space-y-1">
        {edits.map((edit: TransactionEdit) => (
          <p key={edit.id} className="text-xs text-muted-foreground">
            <span className="tabular-nums">
              {editDateFmt.format(new Date(edit.edited_at))}
            </span>
            {" · "}
            <span className="text-foreground">
              {fieldLabels[edit.field_name] ?? edit.field_name}
            </span>
            {": "}
            {formatEditValue(edit.field_name, edit.old_value)}
            {" → "}
            {formatEditValue(edit.field_name, edit.new_value)}
          </p>
        ))}
      </div>
    </div>
  );
}

export function TransactionEditor({
  tx,
  payerName,
  otherName,
  categoryOptions,
  tagOptions,
  saving = false,
  onSave,
  onCancel,
}: TransactionEditorProps) {
  const [date, setDate] = useState(tx.date);
  const [amount, setAmount] = useState(String(tx.amount));
  const [category, setCategory] = useState(tx.category);
  const [tags, setTags] = useState<string[]>([...tx.tags]);
  const [split, setSplit] = useState(String(tx.payer_percentage ?? 50));
  const firstInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    firstInputRef.current?.focus();
  }, []);

  const parsedAmount = Number.parseFloat(amount);
  const parsedSplit = Number.parseInt(split, 10);
  const isSplitValid =
    !Number.isNaN(parsedSplit) && parsedSplit >= 0 && parsedSplit <= 100;
  const isAmountValid = !Number.isNaN(parsedAmount);

  const absAmount = isAmountValid ? Math.abs(parsedAmount) : 0;
  const { payerShare, otherShare } = isSplitValid
    ? computeShares(absAmount, parsedSplit)
    : { payerShare: 0, otherShare: 0 };

  const tagsChanged =
    tags.length !== tx.tags.length || tags.some((t, i) => t !== tx.tags[i]);

  const hasChanges =
    date !== tx.date ||
    (isAmountValid && parsedAmount !== tx.amount) ||
    category !== tx.category ||
    tagsChanged ||
    (isSplitValid && parsedSplit !== (tx.payer_percentage ?? 50));

  const handleSave = useCallback(() => {
    const fields: TransactionUpdateFields = {};
    if (date !== tx.date) fields.date = date;
    if (isAmountValid && parsedAmount !== tx.amount)
      fields.amount = parsedAmount;
    if (category !== tx.category) fields.category = category;
    if (tagsChanged) fields.tags = tags;
    if (isSplitValid && parsedSplit !== (tx.payer_percentage ?? 50))
      fields.payer_percentage = parsedSplit;
    onSave(fields);
  }, [
    date,
    category,
    tags,
    tagsChanged,
    tx,
    parsedAmount,
    parsedSplit,
    isAmountValid,
    isSplitValid,
    onSave,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && hasChanges) {
        e.preventDefault();
        handleSave();
      } else if (e.key === "Escape") {
        onCancel();
      }
    },
    [hasChanges, handleSave, onCancel],
  );

  const inputClass =
    "rounded-md border border-input bg-card px-2 py-1 text-sm text-foreground shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none";

  return (
    <form
      className="py-3"
      onKeyDown={handleKeyDown}
      onSubmit={(e) => e.preventDefault()}
    >
      <p className="mb-2 text-sm text-muted-foreground">
        {formatDate(tx.date)} &middot; {tx.merchant} &middot;{" "}
        {formatCurrency(tx.amount)}
      </p>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="w-16">Date</span>
          <input
            ref={firstInputRef}
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className={`${inputClass} w-40`}
            disabled={saving}
          />
          {tx.original_date && (
            <span className="text-xs text-muted-foreground/60">
              originally {formatDate(tx.original_date)}
            </span>
          )}
        </label>

        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="w-16">Amount</span>
          <input
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className={`${inputClass} w-28 tabular-nums`}
            disabled={saving}
          />
          {tx.original_amount != null && (
            <span className="text-xs text-muted-foreground/60">
              originally {formatCurrency(tx.original_amount)}
            </span>
          )}
        </label>

        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="w-16">Category</span>
          <Combobox
            mode="single"
            options={categoryOptions}
            value={category}
            onChange={(v) => setCategory(v as string)}
            disabled={saving}
            className="w-48"
          />
        </div>

        <div className="flex items-start gap-2 text-sm text-muted-foreground">
          <span className="mt-1.5 w-16">Tags</span>
          <Combobox
            mode="multi"
            options={tagOptions}
            value={tags}
            onChange={(v) => setTags(v as string[])}
            placeholder="shared, s50"
            disabled={saving}
            className="min-w-48 flex-1"
          />
        </div>
      </div>

      <div className="mt-2 flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Split</span>
          <input
            type="number"
            min={0}
            max={100}
            value={split}
            onChange={(e) => setSplit(e.target.value)}
            className={`${inputClass} w-16 tabular-nums`}
            disabled={saving}
          />
          <span>%</span>
        </label>

        {isSplitValid && (
          <span className="text-sm text-muted-foreground tabular-nums">
            {payerName}: {formatCurrency(payerShare)} &middot; {otherName}:{" "}
            {formatCurrency(otherShare)}
          </span>
        )}

        <div className="ml-auto flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={onCancel}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!hasChanges || saving}
            loading={saving}
            loadingText="Saving"
          >
            Save Changes
          </Button>
        </div>
      </div>

      <EditHistory transactionId={tx.id} />
    </form>
  );
}
