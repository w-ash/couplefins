import { Loader2, Lock, LockOpen } from "lucide-react";

interface FinalizationBannerProps {
  isFinalized: boolean;
  finalizedAt: string | null;
  onFinalize: () => void;
  onUnfinalize: () => void;
  isPending: boolean;
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
}: FinalizationBannerProps) {
  if (isFinalized) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-primary-muted bg-primary-muted/40 px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <Lock className="size-4 text-primary-muted-foreground" />
          <span className="text-sm font-medium text-primary-muted-foreground">
            Finalized
            {finalizedAt && (
              <span className="ml-1 font-normal text-primary-muted-foreground/70">
                {formatFinalizedDate(finalizedAt)}
              </span>
            )}
          </span>
        </div>
        <button
          type="button"
          onClick={onUnfinalize}
          disabled={isPending}
          className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium text-primary-muted-foreground/70 transition-colors hover:bg-primary-muted hover:text-primary-muted-foreground disabled:opacity-50"
        >
          {isPending ? (
            <Loader2 className="size-3 animate-spin" />
          ) : (
            <LockOpen className="size-3" />
          )}
          Unlock
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between rounded-lg border border-border-muted px-4 py-2.5">
      <span className="text-sm text-muted-foreground">
        Month not yet finalized
      </span>
      <button
        type="button"
        onClick={onFinalize}
        disabled={isPending}
        className="inline-flex items-center gap-1.5 rounded-md bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/20 disabled:opacity-50"
      >
        {isPending ? (
          <Loader2 className="size-3 animate-spin" />
        ) : (
          <Lock className="size-3" />
        )}
        Finalize
      </button>
    </div>
  );
}
