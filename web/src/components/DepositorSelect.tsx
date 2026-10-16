import { cn } from "@/lib/cn";
import { selectInputClass } from "@/lib/input-styles";

/** Select value meaning "leave the depositor as it is" (bulk edit only). */
export const KEEP_DEPOSITOR = "__keep";

interface DepositorSelectProps {
  owners: Array<{ id: string; name: string }>;
  /** A person id, "" for unassigned, or KEEP_DEPOSITOR. */
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  /** Offer a "No change" option. */
  allowKeep?: boolean;
}

/** Who deposited a joint-account credit. */
export function DepositorSelect({
  owners,
  value,
  onChange,
  disabled = false,
  allowKeep = false,
}: DepositorSelectProps) {
  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      <span className="w-16 shrink-0">Depositor</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={cn(selectInputClass, "w-40")}
      >
        {allowKeep && <option value={KEEP_DEPOSITOR}>No change</option>}
        <option value="">Unassigned</option>
        {owners.map((o) => (
          <option key={o.id} value={o.id}>
            {o.name}
          </option>
        ))}
      </select>
    </label>
  );
}
