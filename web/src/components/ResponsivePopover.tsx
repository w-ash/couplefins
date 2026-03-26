import type { ReactNode } from "react";
import { useCallback, useRef, useState } from "react";
import { BottomSheet } from "@/components/BottomSheet";
import { useIsMobile } from "@/hooks/useIsMobile";
import { useClickOutside } from "@/lib/use-click-outside";

export function ResponsivePopover({
  trigger,
  children,
  onClose,
  popoverClassName,
  title,
}: {
  trigger: ReactNode;
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

  const close = useCallback(() => {
    setOpen(false);
    onClose?.();
  }, [onClose]);

  useClickOutside(ref, open && !isMobile, close);

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen(!open)}>
        {trigger}
      </button>

      {/* Desktop: absolute popover */}
      {open && !isMobile && (
        <div
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
