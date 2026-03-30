import { useEffect, useState } from "react";

export function ProgressBar({
  pct,
  barColor = "bg-primary",
  showLabel = false,
}: {
  pct: number;
  barColor?: string;
  showLabel?: boolean;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    requestAnimationFrame(() => setMounted(true));
  }, []);

  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 rounded-full bg-muted">
        <div
          className={`h-2 rounded-full transition-[width] duration-500 ease-out ${barColor}`}
          style={{ width: mounted ? `${pct}%` : "0%" }}
        />
      </div>
      {showLabel && (
        <span className="w-8 text-right text-xs tabular-nums text-muted-foreground">
          {Math.round(pct)}%
        </span>
      )}
    </div>
  );
}
