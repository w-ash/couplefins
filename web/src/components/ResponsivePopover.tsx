import type { ReactNode } from "react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { BottomSheet } from "@/components/BottomSheet";
import { useIsMobile } from "@/hooks/useIsMobile";
import { useClickOutside } from "@/lib/use-click-outside";

export function ResponsivePopover({
  trigger,
  triggerLabel,
  children,
  onClose,
  popoverClassName,
  title,
}: {
  trigger: ReactNode;
  /** aria-label for the trigger button — required when `trigger` has no visible text */
  triggerLabel?: string;
  children: (close: () => void) => ReactNode;
  onClose?: () => void;
  /** Extra classes for the desktop popover container */
  popoverClassName?: string;
  /** Header shown in the mobile bottom sheet */
  title?: string;
}) {
  const [open, setOpen] = useState(false);
  const isMobile = useIsMobile();
  const ref = useRef<HTMLDivElement>(null);
  const popoverId = useId();

  const close = useCallback(() => {
    setOpen(false);
    onClose?.();
  }, [onClose]);

  useClickOutside(ref, open && !isMobile, close);

  useEffect(() => {
    if (!open || isMobile) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, isMobile, close]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label={triggerLabel}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? popoverId : undefined}
        onClick={() => setOpen(!open)}
      >
        {trigger}
      </button>

      {/* Desktop: absolute popover */}
      {open && !isMobile && (
        <div
          id={popoverId}
          role="dialog"
          aria-label={title ?? triggerLabel}
          className={
            popoverClassName ??
            "absolute left-0 top-full z-50 mt-1.5 min-w-56 overflow-hidden rounded-lg border border-border bg-popover shadow-lg"
          }
        >
          {children(close)}
        </div>
      )}

      {/* Mobile: bottom sheet */}
      {open && isMobile && (
        <BottomSheet open={open} onClose={close}>
          {title && (
            <p className="mb-3 text-sm font-medium text-foreground">{title}</p>
          )}
          <div className="max-h-[60vh] overflow-y-auto">{children(close)}</div>
        </BottomSheet>
      )}
    </div>
  );
}
