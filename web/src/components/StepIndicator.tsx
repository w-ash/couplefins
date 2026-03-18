import { Check } from "lucide-react";

const STEPS = ["Select file", "Preview", "Done"] as const;

interface StepIndicatorProps {
  currentStepIndex: number;
}

export function StepIndicator({ currentStepIndex }: StepIndicatorProps) {
  return (
    <nav aria-label="Upload progress" className="mb-8 flex items-center">
      {STEPS.map((label, i) => {
        const isCompleted = i < currentStepIndex;
        const isCurrent = i === currentStepIndex;

        return (
          <div key={label} className="flex flex-1 items-center last:flex-none">
            {/* Dot + label */}
            <div className="flex flex-col items-center gap-1.5">
              <div
                aria-current={isCurrent ? "step" : undefined}
                className={`flex items-center justify-center rounded-full transition-all duration-500 ${
                  isCompleted
                    ? "size-4 bg-primary"
                    : isCurrent
                      ? "size-2 bg-primary ring-[3px] ring-primary/20"
                      : "size-1.5 bg-border"
                }`}
              >
                {isCompleted && (
                  <Check
                    className="size-2.5 text-primary-foreground"
                    strokeWidth={3}
                  />
                )}
              </div>
              <span
                className={`hidden text-xs sm:block ${
                  isCurrent
                    ? "font-medium text-foreground"
                    : isCompleted
                      ? "text-primary"
                      : "text-muted-foreground"
                }`}
              >
                {label}
              </span>
            </div>

            {/* Connecting line (not after last step) */}
            {i < STEPS.length - 1 && (
              <div className="mx-2 h-0.5 flex-1 rounded-full bg-border">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
                  style={{ width: i < currentStepIndex ? "100%" : "0%" }}
                />
              </div>
            )}
          </div>
        );
      })}
    </nav>
  );
}
