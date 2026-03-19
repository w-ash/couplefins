import { Clock } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  TransactionEditResponse,
  TransactionResponse,
  UpdateTransactionRequest,
} from "@/api/generated/model";
import { useGetTransactionEdits } from "@/api/generated/transactions/transactions";
import { Button } from "@/components/Button";
import type { ComboboxOption } from "@/components/Combobox";
import { Combobox } from "@/components/Combobox";
import { InlineError } from "@/components/InlineError";
import { PercentInput } from "@/components/PercentInput";
import { SegmentedControl } from "@/components/SegmentedControl";
import {
  computeShares,
  formatCurrency,
  formatDate,
  parsePercent,
} from "@/lib/format";
import { baseInputClass, inputErrorClass } from "@/lib/input-styles";
import {
  deriveTransactionType,
  type TransactionType,
  TYPE_OPTIONS,
} from "@/lib/transaction-classification";

interface TransactionEditorProps {
  tx: TransactionResponse;
  payerName: string;
  otherName: string;
  categoryOptions: ComboboxOption[];
  tagOptions: ComboboxOption[];
  saving?: boolean;
  onSave: (fields: UpdateTransactionRequest) => void;
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
  household: "Type",
};

function formatEditValue(fieldName: string, value: string): string {
  if (fieldName === "payer_percentage") return value ? `${value}%` : "—";
  if (fieldName === "household")
    return value === "true" ? "Household" : "Personal";
  if (fieldName === "date" && value) return formatDate(value);
  if (fieldName === "amount" && value) return formatCurrency(Number(value));
  return value || "—";
}

function EditHistory({ transactionId }: { transactionId: string }) {
  const { data: response } = useGetTransactionEdits(transactionId);
  const edits = (response?.status === 200 ? response.data.edits : null) ?? [];
  if (edits.length === 0) return null;

  return (
    <div className="mt-3 border-t border-border-muted pt-3">
      <p className="mb-1.5 flex items-center gap-1 text-sm font-medium text-muted-foreground">
        <Clock className="size-3" />
        Edit History
      </p>
      <div className="space-y-1.5">
        {edits.map((edit: TransactionEditResponse) => (
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
  const originalType = deriveTransactionType(tx.household, tx.payer_percentage);

  const [date, setDate] = useState(tx.date);
  const [amount, setAmount] = useState(String(tx.amount));
  const [category, setCategory] = useState(tx.category);
  const [tags, setTags] = useState<string[]>([...tx.tags]);
  const [split, setSplit] = useState(String(tx.payer_percentage));
  const [household, setHousehold] = useState(tx.household);
  const firstInputRef = useRef<HTMLInputElement>(null);

  const currentType = deriveTransactionType(
    household,
    parsePercent(split) ?? tx.payer_percentage,
  );
  const splitEditable = currentType === "shared";

  useEffect(() => {
    firstInputRef.current?.focus();
  }, []);

  const handleTypeChange = useCallback(
    (type: TransactionType) => {
      switch (type) {
        case "personal":
          setHousehold(false);
          setSplit("100");
          break;
        case "shared":
          setHousehold(true);
          // Restore original split if the tx was originally shared, otherwise default 50
          setSplit(
            originalType === "shared" ? String(tx.payer_percentage) : "50",
          );
          break;
        case "spotted":
          setHousehold(true);
          setSplit("0");
          break;
        case "household":
          setHousehold(true);
          setSplit("100");
          break;
      }
    },
    [originalType, tx.payer_percentage],
  );

  const parsedAmount = Number.parseFloat(amount);
  const parsedSplit = parsePercent(split);
  const isSplitValid = parsedSplit !== null;
  const isAmountValid = !Number.isNaN(parsedAmount);
  const splitChanged = split !== "" && split !== String(tx.payer_percentage);
  const amountChanged = amount !== "" && amount !== String(tx.amount);
  const householdChanged = household !== tx.household;

  const absAmount = isAmountValid ? Math.abs(parsedAmount) : 0;
  const { payerShare, otherShare } =
    parsedSplit !== null
      ? computeShares(absAmount, parsedSplit)
      : { payerShare: 0, otherShare: 0 };

  const tagsChanged =
    tags.length !== tx.tags.length || tags.some((t, i) => t !== tx.tags[i]);

  const hasChanges =
    date !== tx.date ||
    (isAmountValid && parsedAmount !== tx.amount) ||
    category !== tx.category ||
    tagsChanged ||
    householdChanged ||
    (parsedSplit !== null && parsedSplit !== tx.payer_percentage);

  const handleSave = useCallback(() => {
    const fields: UpdateTransactionRequest = {};
    if (date !== tx.date) fields.date = date;
    if (isAmountValid && parsedAmount !== tx.amount)
      fields.amount = parsedAmount;
    if (category !== tx.category) fields.category = category;
    if (tagsChanged) fields.tags = tags;
    if (parsedSplit !== null && parsedSplit !== tx.payer_percentage)
      fields.payer_percentage = parsedSplit;
    if (householdChanged) fields.household = household;
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
    household,
    householdChanged,
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

  const splitHasError = splitChanged && !isSplitValid;
  const amountHasError = amountChanged && !isAmountValid;

  return (
    <form
      className="py-3"
      onKeyDown={handleKeyDown}
      onSubmit={(e) => e.preventDefault()}
    >
      <div className="mb-3 flex items-center gap-2 text-sm">
        <span className="font-medium text-foreground">{tx.merchant}</span>
        <span className="text-muted-foreground">&middot;</span>
        <span className="tabular-nums text-foreground">
          {formatCurrency(tx.amount)}
        </span>
        <span className="text-muted-foreground">&middot;</span>
        <span className="tabular-nums text-muted-foreground">
          {formatDate(tx.date)}
        </span>
      </div>

      <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
        <span className="w-16 shrink-0">Type</span>
        <SegmentedControl<TransactionType>
          options={TYPE_OPTIONS}
          value={currentType}
          onChange={handleTypeChange}
          size="sm"
          shape="pill"
        />
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-3">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="w-16 shrink-0">Date</span>
          <input
            ref={firstInputRef}
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className={`${baseInputClass} w-40`}
            disabled={saving}
          />
          {tx.original_date && (
            <span className="text-xs italic text-muted-foreground">
              originally {formatDate(tx.original_date)}
            </span>
          )}
        </label>

        <div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="w-16 shrink-0">Amount</span>
            <input
              type="number"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={`${baseInputClass} w-28 tabular-nums ${amountHasError ? inputErrorClass : ""}`}
              disabled={saving}
              aria-invalid={amountHasError || undefined}
              aria-describedby={amountHasError ? "amount-error" : undefined}
            />
            {tx.original_amount != null && (
              <span className="text-xs italic text-muted-foreground">
                originally {formatCurrency(tx.original_amount)}
              </span>
            )}
          </label>
          {amountHasError && (
            <div id="amount-error" className="mt-1 pl-18">
              <InlineError>Enter a valid number</InlineError>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="w-16 shrink-0">Category</span>
          <Combobox
            mode="single"
            options={categoryOptions}
            value={category}
            onChange={(v) => setCategory(v as string)}
            disabled={saving}
            className="flex-1"
          />
        </div>

        <div className="flex items-start gap-2 text-sm text-muted-foreground">
          <span className="mt-2 w-16 shrink-0">Tags</span>
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

      <div className="mt-3 flex flex-wrap items-center gap-4">
        <label
          htmlFor="tx-split"
          className="flex items-center gap-2 text-sm text-muted-foreground"
        >
          <span className="w-16 shrink-0">Split</span>
          <PercentInput
            id="tx-split"
            value={split}
            onChange={setSplit}
            disabled={saving || !splitEditable}
            error={splitHasError}
          />
        </label>

        <div aria-live="polite">
          {!splitHasError && isSplitValid ? (
            <span className="text-sm tabular-nums text-muted-foreground">
              {payerName}: {formatCurrency(payerShare)} &middot; {otherName}:{" "}
              {formatCurrency(otherShare)}
            </span>
          ) : null}
        </div>

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
