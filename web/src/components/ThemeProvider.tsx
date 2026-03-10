import type { ReactNode } from "react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  applyTheme,
  getStoredTheme,
  resolveIsDark,
  storeTheme,
  type Theme,
} from "@/lib/theme";

interface ThemeContextValue {
  theme: Theme;
  isDark: boolean;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getStoredTheme);
  const [isDark, setIsDark] = useState(() => resolveIsDark(getStoredTheme()));

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    storeTheme(next);
    applyTheme(next);
    setIsDark(resolveIsDark(next));
  }, []);

  // Apply on mount (sync with FOIT script); setTheme owns subsequent changes
  // biome-ignore lint/correctness/useExhaustiveDependencies: mount-only effect
  useEffect(() => {
    applyTheme(theme);
  }, []);

  // Listen for OS theme changes when in "system" mode
  useEffect(() => {
    if (theme !== "system") return;

    const handler = () => {
      applyTheme("system");
      setIsDark(resolveIsDark("system"));
    };
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  const value = useMemo(
    () => ({ theme, isDark, setTheme }),
    [theme, isDark, setTheme],
  );

  return <ThemeContext value={value}>{children}</ThemeContext>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
