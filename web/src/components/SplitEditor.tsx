import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { computeShares, formatCurrency } from "@/lib/format";

export const percentInputClass =
  "w-16 rounded-md border border-input bg-card px-2 py-1 text-sm text-foreground tabular-nums shadow-sm focus:border-ring focus:ring-1 focus:ring-ring focus:outline-none";

interface SplitEditorProps {
  /** Current payer percentage (0-100) */
  currentPercentage: number;
  /** Absolute transaction amount (always positive) */
  absAmount: number;
  /** Name of the payer */
  payerName: string;
  /** Name of the other person */
  otherName: string;
  /** Whether the save is in progress */
  saving?: boolean;
  /** Auto-focus the input on mount */
  autoFocus?: boolean;
  onSave: (newPercentage: number) => void;
  onCancel: () => void;
}

export function SplitEditor({
  currentPercentage,
  absAmount,
  payerName,
  otherName,
  saving = false,
  autoFocus = false,
  onSave,
  onCancel,
}: SplitEditorProps) {
  const [value, setValue] = useState(String(currentPercentage));
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [autoFocus]);

  const parsed = Number.parseInt(value, 10);
  const isValid = !Number.isNaN(parsed) && parsed >= 0 && parsed <= 100;
  const hasChanged = isValid && parsed !== currentPercentage;

  const { payerShare, otherShare } = isValid
    ? computeShares(absAmount, parsed)
    : { payerShare: 0, otherShare: 0 };

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && isValid && hasChanged) {
        onSave(parsed);
      } else if (e.key === "Escape") {
        onCancel();
      }
    },
    [isValid, hasChanged, parsed, onSave, onCancel],
  );

  return (
    <div className="flex items-center gap-4 py-2">
      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        <span>Split</span>
        <input
          ref={inputRef}
          type="number"
          min={0}
          max={100}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          className={percentInputClass}
          disabled={saving}
        />
        <span>%</span>
      </label>

      {isValid && (
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
          onClick={() => onSave(parsed)}
          disabled={!isValid || !hasChanged || saving}
          loading={saving}
          loadingText="Saving"
        >
          Save Split
        </Button>
      </div>
    </div>
  );
}
