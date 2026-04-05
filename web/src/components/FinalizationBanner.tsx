import { Lock, LockOpen } from "lucide-react";
import { Button } from "@/components/Button";

interface FinalizationBannerProps {
  isFinalized: boolean;
  finalizedAt: string | null;
  onFinalize: () => void;
  onUnfinalize: () => void;
  isPending: boolean;
  warnings?: string[];
}

function formatFinalizedDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function FinalizationBanner({
  isFinalized,
  finalizedAt,
  onFinalize,
  onUnfinalize,
  isPending,
  warnings,
}: FinalizationBannerProps) {
  if (isFinalized) {
    return (
      <div className="flex flex-col gap-2 rounded-lg border border-primary-muted bg-primary-muted/40 px-4 py-2.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2.5">
          <Lock
            className="size-4 text-primary-muted-foreground"
            strokeWidth={2.5}
          />
          <span className="text-sm font-medium text-primary-muted-foreground">
            Month locked
            {finalizedAt && (
              <span className="ml-1 font-normal text-primary-muted-foreground/70">
                {formatFinalizedDate(finalizedAt)}
              </span>
            )}
          </span>
        </div>
        <Button
          variant="secondary"
          size="sm"
          icon={<LockOpen className="size-3" strokeWidth={2.5} />}
          onClick={onUnfinalize}
          loading={isPending}
          loadingText="Unlocking"
        >
          Unlock Month
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border-muted px-4 py-2.5 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <span className="text-sm text-muted-foreground">
          This month is still open for changes
        </span>
        <p className="text-xs text-muted-foreground/70">
          Lock it once you've both reviewed and settled up.
        </p>
        {warnings && warnings.length > 0 && (
          <ul className="mt-1 space-y-0.5">
            {warnings.map((w) => (
              <li key={w} className="text-xs text-warning-muted-foreground">
                {w}
              </li>
            ))}
          </ul>
        )}
      </div>
      <Button
        size="sm"
        icon={<LockOpen className="size-3" strokeWidth={2.5} />}
        onClick={onFinalize}
        loading={isPending}
        loadingText="Locking"
      >
        Lock Month
      </Button>
    </div>
  );
}
