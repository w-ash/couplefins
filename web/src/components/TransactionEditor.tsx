import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  TransactionResponse,
  UpdateTransactionRequest,
} from "@/api/generated/model";
import { Button } from "@/components/Button";
import type { ComboboxOption } from "@/components/Combobox";
import { Combobox } from "@/components/Combobox";
import { DepositorSelect } from "@/components/DepositorSelect";
import { InlineError } from "@/components/InlineError";
import {
  OwnerSharesEditor,
  useOwnerShares,
} from "@/components/OwnerSharesEditor";
import { PercentInput } from "@/components/PercentInput";
import { SegmentedControl } from "@/components/SegmentedControl";
import { TransactionEditHistory } from "@/components/TransactionEditHistory";
import { cn } from "@/lib/cn";
import {
  computeShares,
  formatCurrency,
  formatDate,
  parsePercent,
} from "@/lib/format";
import { baseInputClass, inputErrorClass } from "@/lib/input-styles";
import type { TransactionScope } from "@/lib/transaction-filters";

interface TransactionEditorProps {
  tx: TransactionResponse;
  payerName: string;
  otherName: string;
  categoryOptions: ComboboxOption[];
  tagOptions: ComboboxOption[];
  personNames: Map<string, string>;
  saving?: boolean;
  onSave: (fields: UpdateTransactionRequest) => void;
  onCancel: () => void;
}

export function TransactionEditor({
  tx,
  payerName,
  otherName,
  categoryOptions,
  tagOptions,
  personNames,
  saving = false,
  onSave,
  onCancel,
}: TransactionEditorProps) {
  const [date, setDate] = useState(tx.date);
  const [amount, setAmount] = useState(String(tx.amount));
  const [category, setCategory] = useState(tx.category);
  const [tags, setTags] = useState<string[]>([...tx.tags]);
  const [notes, setNotes] = useState(tx.notes);
  const [split, setSplit] = useState(String(tx.payer_percentage));
  const [household, setHousehold] = useState(tx.household);
  const [isExcluded, setIsExcluded] = useState(tx.is_excluded);
  const firstInputRef = useRef<HTMLInputElement>(null);

  const isJoint = tx.is_joint;
  const owners = useMemo(
    () => [...personNames].map(([id, name]) => ({ id, name })),
    [personNames],
  );
  const ownerShares = useOwnerShares(
    owners,
    owners[0] ? (tx.shares[owners[0].id] ?? 50) : 50,
  );
  const [depositor, setDepositor] = useState(tx.depositor_person_id ?? "");

  const scopeValue: TransactionScope = household ? "household" : "personal";

  useEffect(() => {
    firstInputRef.current?.focus();
  }, []);

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

  const excludedChanged = isExcluded !== tx.is_excluded;
  const notesChanged = notes !== tx.notes;

  const ownerSharesInvalid = isJoint && ownerShares.invalid;
  // undefined = leave unchanged; null = reset to 50/50.
  let ownerSharesChange: Record<string, number> | null | undefined;
  if (isJoint) {
    if (ownerShares.reset) {
      if (tx.owner_shares !== null) ownerSharesChange = null;
    } else if (ownerShares.edited) ownerSharesChange = ownerShares.payload;
  }
  const depositorChanged =
    isJoint && depositor !== (tx.depositor_person_id ?? "");

  const hasChanges =
    ownerSharesChange !== undefined ||
    depositorChanged ||
    date !== tx.date ||
    (isAmountValid && parsedAmount !== tx.amount) ||
    category !== tx.category ||
    tagsChanged ||
    notesChanged ||
    householdChanged ||
    excludedChanged ||
    (parsedSplit !== null && parsedSplit !== tx.payer_percentage);

  const handleSave = useCallback(() => {
    const fields: UpdateTransactionRequest = {};
    if (date !== tx.date) fields.date = date;
    if (isAmountValid && parsedAmount !== tx.amount)
      fields.amount = parsedAmount;
    if (category !== tx.category) fields.category = category;
    if (tagsChanged) fields.tags = tags;
    if (notesChanged) fields.notes = notes;
    if (!isJoint && parsedSplit !== null && parsedSplit !== tx.payer_percentage)
      fields.payer_percentage = parsedSplit;
    if (ownerSharesChange !== undefined)
      fields.owner_shares = ownerSharesChange;
    if (depositorChanged) fields.depositor_person_id = depositor || null;
    if (householdChanged) fields.household = household;
    if (excludedChanged) fields.is_excluded = isExcluded;
    onSave(fields);
  }, [
    date,
    category,
    tags,
    tagsChanged,
    notes,
    notesChanged,
    tx,
    parsedAmount,
    parsedSplit,
    isAmountValid,
    household,
    householdChanged,
    isExcluded,
    excludedChanged,
    onSave,
    isJoint,
    ownerSharesChange,
    depositor,
    depositorChanged,
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

  const splitHasError = !isJoint && splitChanged && !isSplitValid;
  const amountHasError = amountChanged && !isAmountValid;

  return (
    <form
      className="py-3"
      onKeyDown={handleKeyDown}
      onSubmit={(e) => e.preventDefault()}
    >
      {!isJoint && (
        <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
          <span className="w-16 shrink-0">Scope</span>
          <SegmentedControl<TransactionScope>
            options={[
              { value: "household", label: "Household" },
              { value: "personal", label: "Personal" },
            ]}
            value={scopeValue}
            onChange={(v) => setHousehold(v === "household")}
            size="sm"
            shape="pill"
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-x-6 sm:gap-y-3">
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="w-16 shrink-0">Date</span>
          <input
            ref={firstInputRef}
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className={cn(baseInputClass, "w-40")}
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
              inputMode="decimal"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={cn(
                baseInputClass,
                "w-28 tabular-nums",
                amountHasError && inputErrorClass,
              )}
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

      <label className="mt-3 flex items-start gap-2 text-sm text-muted-foreground">
        <span className="mt-2 w-16 shrink-0">Notes</span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className={cn(baseInputClass, "flex-1 resize-y")}
          disabled={saving}
        />
      </label>

      {isJoint ? (
        <div className="mt-3 space-y-3">
          {ownerShares.pair && (
            <OwnerSharesEditor
              owners={ownerShares.pair}
              values={ownerShares.values}
              absAmount={absAmount}
              disabled={saving}
              isDefault={tx.owner_shares === null && !ownerShares.edited}
              onChange={ownerShares.onChange}
              onReset={ownerShares.onReset}
            />
          )}
          {ownerSharesInvalid && (
            <InlineError>Shares must be 0–100</InlineError>
          )}
          {tx.amount > 0 && (
            <DepositorSelect
              owners={owners}
              value={depositor}
              onChange={setDepositor}
              disabled={saving}
            />
          )}
        </div>
      ) : (
        <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
          <span className="w-16 shrink-0">Split</span>
          <PercentInput
            id="tx-split"
            value={split}
            onChange={setSplit}
            disabled={saving}
            error={splitHasError}
          />
          <div aria-live="polite">
            {!splitHasError && isSplitValid ? (
              <span className="tabular-nums">
                {payerName}: {formatCurrency(payerShare)} &middot; {otherName}:{" "}
                {formatCurrency(otherShare)}
              </span>
            ) : null}
          </div>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-4">
        <label
          className="flex items-center gap-2 text-sm text-muted-foreground"
          title="Excluded transactions don't count toward settlement or budget"
        >
          <input
            type="checkbox"
            checked={isExcluded}
            onChange={(e) => setIsExcluded(e.target.checked)}
            disabled={saving}
            className="size-4 accent-primary"
          />
          Exclude
        </label>

        <div className="flex w-full gap-2 sm:ml-auto sm:w-auto">
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

      <TransactionEditHistory transactionId={tx.id} personNames={personNames} />
    </form>
  );
}
