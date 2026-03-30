import {
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";

interface SegmentedControlProps<T extends string> {
  options: Array<{ value: T; label: string; icon?: ReactNode }>;
  value: T;
  onChange: (value: T) => void;
  size?: "sm" | "default";
  shape?: "rounded" | "pill";
}

const shapeClasses = {
  rounded: "rounded-lg",
  pill: "rounded-full",
} as const;

const sizeClasses = {
  sm: "py-1.5 text-xs",
  default: "py-1.5 text-sm",
} as const;

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  size = "default",
  shape = "rounded",
}: SegmentedControlProps<T>) {
  const groupName = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const labelRefs = useRef<Map<T, HTMLLabelElement>>(new Map());
  const [indicator, setIndicator] = useState<{
    left: number;
    width: number;
  } | null>(null);

  const shapeClass = shapeClasses[shape];
  const sizeClass = sizeClasses[size];

  // Measure and position the sliding indicator
  const updateIndicator = useCallback(() => {
    const el = labelRefs.current.get(value);
    if (!el) return;
    setIndicator({ left: el.offsetLeft, width: el.offsetWidth });
  }, [value]);

  useEffect(() => {
    updateIndicator();
  }, [updateIndicator]);

  // Re-measure on resize
  useEffect(() => {
    if (typeof ResizeObserver === "undefined" || !containerRef.current) return;
    const observer = new ResizeObserver(updateIndicator);
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [updateIndicator]);

  return (
    <div
      ref={containerRef}
      role="radiogroup"
      className={`relative flex ${shapeClass} bg-muted/50 p-0.5`}
    >
      {/* Sliding indicator */}
      {indicator && (
        <div
          aria-hidden
          className={`absolute top-0.5 bottom-0.5 ${shapeClass} bg-card shadow-sm transition-[transform,width] duration-200 ease-out`}
          style={{
            transform: `translateX(${indicator.left}px)`,
            width: indicator.width,
            left: 0,
          }}
        />
      )}

      {/* Options — native radio inputs for accessibility + keyboard nav */}
      {options.map((option) => {
        const isActive = option.value === value;
        return (
          <label
            key={option.value}
            ref={(el) => {
              if (el) labelRefs.current.set(option.value, el);
            }}
            className={`relative z-10 flex-1 cursor-pointer select-none whitespace-nowrap text-center has-focus-visible:outline-none has-focus-visible:ring-2 has-focus-visible:ring-ring inline-flex items-center justify-center gap-1.5 ${shapeClass} px-3 ${sizeClass} font-medium transition-colors duration-150 ${
              isActive
                ? "text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <input
              type="radio"
              name={groupName}
              value={option.value}
              checked={isActive}
              onChange={() => onChange(option.value)}
              className="sr-only"
            />
            {option.icon}
            {option.label}
          </label>
        );
      })}
    </div>
  );
}
