import { AlertTriangle } from "lucide-react";

export function InlineError({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="flex items-center gap-1.5 text-sm text-negative"
      role="alert"
    >
      <AlertTriangle className="size-3.5" />
      {children}
    </span>
  );
}
