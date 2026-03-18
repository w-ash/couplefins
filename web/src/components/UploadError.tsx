import { CircleAlert } from "lucide-react";

interface UploadErrorProps {
  error: Error | unknown;
}

export function UploadError({ error }: UploadErrorProps) {
  const message = error instanceof Error ? error.message : "An error occurred";
  const lines = message.split("\n");

  return (
    <div
      role="alert"
      className="mt-4 flex items-start gap-2.5 rounded-lg border border-destructive-border bg-destructive-muted p-4 text-sm text-destructive-muted-foreground"
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" />
      <div>
        {lines.length === 1 ? (
          message
        ) : (
          <ul className="list-inside list-disc space-y-1">
            {lines.map((line, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: static error lines
              <li key={i}>{line}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
