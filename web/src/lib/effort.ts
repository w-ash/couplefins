// Per-request effort for the chat assistant. The user picks per task —
// quick lookups don't need deep reasoning, audits do. Mirrors the backend
// EffortLevel subset the UI exposes (ChatRequest.effort).

export type EffortChoice = "quick" | "standard" | "thorough";

const STORAGE_KEY = "couplefins:chatEffort";

export const EFFORT_API_VALUES: Record<EffortChoice, string> = {
  quick: "low",
  standard: "high",
  thorough: "xhigh",
};

export const EFFORT_OPTIONS: Array<{ value: EffortChoice; label: string }> = [
  { value: "quick", label: "Quick" },
  { value: "standard", label: "Standard" },
  { value: "thorough", label: "Thorough" },
];

export function getStoredEffort(): EffortChoice {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "quick" || stored === "standard" || stored === "thorough") {
      return stored;
    }
  } catch {
    // Private browsing or storage unavailable
  }
  return "standard";
}

export function storeEffort(choice: EffortChoice): void {
  try {
    localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    // Silently fail
  }
}
