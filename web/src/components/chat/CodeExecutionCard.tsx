import { Check, Loader2, SquareTerminal } from "lucide-react";
import { useState } from "react";
import { ExpandChevron } from "@/components/ExpandChevron";
import type { CodeExecution } from "@/lib/chat";
import { cn } from "@/lib/cn";

const monoBlockClass =
  "overflow-x-auto rounded-lg bg-background p-3 font-mono text-xs leading-normal";

function statusLabel(execution: CodeExecution): string {
  if (execution.returnCode === undefined) return "Running code…";
  if (execution.returnCode !== 0)
    return `Code failed (exit ${execution.returnCode})`;
  return "Ran code";
}

export function CodeExecutionCard({ execution }: { execution: CodeExecution }) {
  const [expanded, setExpanded] = useState(false);
  const isRunning = execution.returnCode === undefined;
  const failed = !isRunning && execution.returnCode !== 0;
  const hasOutput = Boolean(execution.stdout || execution.stderr);

  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <SquareTerminal className="size-3.5" />
        {isRunning ? (
          <Loader2 className="size-3 animate-spin" />
        ) : (
          <Check className="size-3" />
        )}
        <span className={cn(failed && "text-destructive-muted-foreground")}>
          {statusLabel(execution)}
        </span>
      </div>
      <pre className={cn(monoBlockClass, "mt-2 max-h-48")}>
        {execution.command}
      </pre>
      {hasOutput && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="mt-2 flex items-center gap-1 rounded-md text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          <ExpandChevron expanded={expanded} />
          {expanded ? "Hide output" : "Show output"}
        </button>
      )}
      {expanded && hasOutput && (
        <div className="mt-2 flex flex-col gap-2">
          {execution.stdout && (
            <pre className={monoBlockClass}>{execution.stdout}</pre>
          )}
          {execution.stderr && (
            <pre
              className={cn(
                monoBlockClass,
                "text-destructive-muted-foreground",
              )}
            >
              {execution.stderr}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
