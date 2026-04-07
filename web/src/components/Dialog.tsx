import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useDialogSync } from "@/hooks/useDialogSync";

type DialogSize = "sm" | "default";

const sizes: Record<DialogSize, string> = {
  default: "max-w-lg",
  sm: "max-w-sm",
};

export function Dialog({
  open,
  onClose,
  size = "default",
  children,
  ...rest
}: {
  open: boolean;
  onClose: () => void;
  size?: DialogSize;
  children: ReactNode;
  "aria-labelledby"?: string;
}) {
  const dialogRef = useDialogSync(open);

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      className={`mx-4 w-full ${sizes[size]} rounded-xl border border-border bg-card p-6 shadow-lg backdrop:bg-black/40`}
      {...rest}
    >
      {children}
    </dialog>
  );
}

type DialogHeaderProps = {
  title: string;
  onClose?: () => void;
} & (
  | { subtitle?: string; children?: never }
  | { subtitle?: never; children: ReactNode }
);

export function DialogHeader({
  title,
  subtitle,
  onClose,
  children,
}: DialogHeaderProps) {
  return (
    <div className="flex items-start justify-between">
      <div>
        <h2 className="text-lg font-medium text-foreground">{title}</h2>
        {children ??
          (subtitle && (
            <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>
          ))}
      </div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="rounded-md p-1 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="size-4" />
        </button>
      )}
    </div>
  );
}

export function DialogFooter({ children }: { children: ReactNode }) {
  return (
    <div className="mt-5 flex items-center justify-end gap-3">{children}</div>
  );
}
