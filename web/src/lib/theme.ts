export type Theme = "system" | "light" | "dark";

// Mirrored in index.html FOIT-prevention script — update both together
const STORAGE_KEY = "couplefins:theme";

export function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // Private browsing or storage unavailable
  }
  return "system";
}

export function storeTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Silently fail
  }
}

export function resolveIsDark(theme: Theme): boolean {
  if (theme === "dark") return true;
  if (theme === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function applyTheme(theme: Theme): void {
  const isDark = resolveIsDark(theme);
  document.documentElement.classList.toggle("dark", isDark);
}
