import { useCallback, useMemo, useState } from "react";
import { Button } from "@/components/Button";
import { PercentInput } from "@/components/PercentInput";
import { computeShares, formatCurrency, parsePercent } from "@/lib/format";

export interface OwnerShareOwner {
  id: string;
  name: string;
}

export interface OwnerSharesState {
  /** The two owners, or null when the household is not a couple. */
  pair: [OwnerShareOwner, OwnerShareOwner] | null;
  values: [string, string];
  /** True after "Reset to 50/50" until the next edit. */
  reset: boolean;
  /** The first owner's parsed percent, or null when blank or invalid. */
  firstShare: number | null;
  /** True when the entered shares cannot be saved. */
  invalid: boolean;
  /** True when the first share parses and differs from the initial one. */
  edited: boolean;
  /** Request value: null resets to 50/50, undefined means no usable input. */
  payload: Record<string, number> | null | undefined;
  onChange: (values: [string, string]) => void;
  onReset: () => void;
}

/**
 * Owner-share form state for joint rows.
 * `initial` is the first owner's percent; null starts blank (bulk edit).
 */
export function useOwnerShares(
  owners: OwnerShareOwner[],
  initial: number | null,
): OwnerSharesState {
  const pair = useMemo<[OwnerShareOwner, OwnerShareOwner] | null>(
    () => (owners.length === 2 ? [owners[0], owners[1]] : null),
    [owners],
  );
  const [values, setValues] = useState<[string, string]>(
    initial === null ? ["", ""] : [String(initial), String(100 - initial)],
  );
  const [reset, setReset] = useState(false);

  const onChange = useCallback((next: [string, string]) => {
    setValues(next);
    setReset(false);
  }, []);
  const onReset = useCallback(() => {
    setValues(["50", "50"]);
    setReset(true);
  }, []);

  const firstShare = parsePercent(values[0]);
  const secondShare = parsePercent(values[1]);
  const blank = values[0] === "" && values[1] === "";
  const invalid =
    !reset &&
    (initial !== null || !blank) &&
    (firstShare === null || secondShare === null);
  const edited = !reset && firstShare !== null && firstShare !== initial;
  const payload = useMemo<OwnerSharesState["payload"]>(() => {
    if (reset) return null;
    if (pair && firstShare !== null)
      return { [pair[0].id]: firstShare, [pair[1].id]: 100 - firstShare };
    return undefined;
  }, [reset, pair, firstShare]);

  return {
    pair,
    values,
    reset,
    firstShare,
    invalid,
    edited,
    payload,
    onChange,
    onReset,
  };
}

interface OwnerSharesEditorProps {
  /** The two owners, in persons order. */
  owners: [OwnerShareOwner, OwnerShareOwner];
  /** Percent text for each owner, same order as `owners`. */
  values: [string, string];
  /** Absolute transaction amount; omit to hide the dollar preview. */
  absAmount?: number;
  disabled?: boolean;
  /** Whether the row currently has no override (shares are the 50/50 default). */
  isDefault: boolean;
  onChange: (values: [string, string]) => void;
  onReset: () => void;
}

/** Complementary percent inputs for a joint row's owner shares. */
export function OwnerSharesEditor({
  owners,
  values,
  absAmount,
  disabled = false,
  isDefault,
  onChange,
  onReset,
}: OwnerSharesEditorProps) {
  const setOwner = (index: 0 | 1, text: string) => {
    const parsed = parsePercent(text);
    const other = parsed === null ? "" : String(100 - parsed);
    onChange(index === 0 ? [text, other] : [other, text]);
  };

  const first = parsePercent(values[0]);
  const second = parsePercent(values[1]);
  const valid = first !== null && second !== null;
  const amounts =
    valid && absAmount !== undefined ? computeShares(absAmount, first) : null;

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
      <span className="w-16 shrink-0">Shares</span>
      {owners.map((owner, i) => {
        const index = i as 0 | 1;
        const parsed = index === 0 ? first : second;
        const id = `tx-owner-share-${owner.id}`;
        return (
          <label
            key={owner.id}
            htmlFor={id}
            className="flex items-center gap-2"
          >
            <span>{owner.name}</span>
            <PercentInput
              id={id}
              value={values[index]}
              onChange={(text) => setOwner(index, text)}
              disabled={disabled}
              error={values[index] !== "" && parsed === null}
            />
          </label>
        );
      })}
      <Button
        variant="secondary"
        size="sm"
        onClick={onReset}
        disabled={disabled || isDefault}
      >
        Reset to 50/50
      </Button>
      <div aria-live="polite" className="tabular-nums">
        {amounts
          ? `${owners[0].name}: ${formatCurrency(amounts.payerShare)} · ${owners[1].name}: ${formatCurrency(amounts.otherShare)}`
          : null}
      </div>
    </div>
  );
}
