import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { PercentInput } from "@/components/PercentInput";
import { computeShares, formatCurrency, parsePercent } from "@/lib/format";

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

  const parsed = parsePercent(value);
  const isValid = parsed !== null;
  const hasChanged = isValid && parsed !== currentPercentage;

  const { payerShare, otherShare } =
    parsed !== null
      ? computeShares(absAmount, parsed)
      : { payerShare: 0, otherShare: 0 };

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && parsed !== null && hasChanged) {
        onSave(parsed);
      } else if (e.key === "Escape") {
        onCancel();
      }
    },
    [hasChanged, parsed, onSave, onCancel],
  );

  return (
    <div className="flex items-center gap-4 py-2">
      <label
        htmlFor="inline-split"
        className="flex items-center gap-2 text-sm text-muted-foreground"
      >
        <span>Split</span>
        <PercentInput
          id="inline-split"
          inputRef={inputRef}
          value={value}
          onChange={setValue}
          onKeyDown={handleKeyDown}
          disabled={saving}
          error={undefined}
        />
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
          onClick={() => {
            if (parsed !== null) onSave(parsed);
          }}
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
