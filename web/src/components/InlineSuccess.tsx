import { CheckCircle2 } from "lucide-react";

export function InlineSuccess({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="flex items-center gap-1.5 text-sm text-positive"
      aria-live="polite"
    >
      <CheckCircle2 className="size-3.5" />
      {children}
    </span>
  );
}
