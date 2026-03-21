import type { ReactNode } from "react";
import { useDialogSync } from "@/hooks/useDialogSync";

export function BottomSheet({
  open,
  onClose,
  variant = "sheet",
  children,
}: {
  open: boolean;
  onClose: () => void;
  variant?: "sheet" | "fullscreen";
  children: ReactNode;
}) {
  const dialogRef = useDialogSync(open);

  const shared =
    "z-50 m-0 w-full max-w-full bg-popover p-0 shadow-lg backdrop:bg-black/20";
  const isFullscreen = variant === "fullscreen";

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      className={
        isFullscreen
          ? `fixed inset-0 h-full max-h-full ${shared}`
          : `fixed inset-auto bottom-0 left-0 right-0 rounded-t-2xl border-t border-border ${shared}`
      }
    >
      <div
        className={
          isFullscreen ? "h-full" : "px-4 pb-[env(safe-area-inset-bottom)] pt-3"
        }
      >
        {!isFullscreen && (
          <div className="mb-3 flex justify-center">
            <div className="h-1 w-8 rounded-full bg-muted-foreground/30" />
          </div>
        )}
        {children}
      </div>
    </dialog>
  );
}
