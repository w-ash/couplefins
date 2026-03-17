import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import type { MonthReference } from "@/api/generated/model";
import { Button } from "@/components/Button";
import { MONTHS } from "@/lib/format";

export function PageLoading({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-muted-foreground">
      <Loader2 className="size-5 animate-spin" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function PageError({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry: () => void;
}) {
  const message =
    error instanceof Error ? error.message : "An unexpected error occurred";

  return (
    <div
      role="alert"
      className="rounded-lg border border-destructive-border bg-destructive-muted p-4"
    >
      <p className="text-sm text-destructive-muted-foreground">{message}</p>
      <Button variant="secondary" size="sm" onClick={onRetry} className="mt-3">
        Try Again
      </Button>
    </div>
  );
}

export function PageEmpty({
  icon,
  heading,
  description,
  action,
}: {
  icon: ReactNode;
  heading: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center py-16 text-center">
      <div className="text-muted-foreground [&>svg]:size-10">{icon}</div>
      <h2 className="mt-4 text-lg font-medium text-foreground">{heading}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/**
 * Shared action links for empty states: "Upload CSV" with an optional
 * "or View [Month Year]" link when a different month has data.
 */
export function EmptyStateActions({
  latestMonth,
  currentYear,
  currentMonth,
  viewPath,
}: {
  latestMonth: MonthReference | null;
  currentYear: number;
  currentMonth: number;
  viewPath: string;
}) {
  const hasOtherMonth =
    latestMonth &&
    (latestMonth.year !== currentYear || latestMonth.month !== currentMonth);

  return (
    <div className="flex items-center gap-3">
      <Link
        to="/upload"
        className="text-sm font-medium text-primary hover:underline"
      >
        Upload CSV
      </Link>
      {hasOtherMonth && (
        <>
          <span className="text-sm text-muted-foreground">or</span>
          <Link
            to={`/${viewPath}?year=${latestMonth.year}&month=${latestMonth.month}`}
            className="text-sm font-medium text-primary hover:underline"
          >
            View {MONTHS[latestMonth.month - 1]} {latestMonth.year}
          </Link>
        </>
      )}
    </div>
  );
}
