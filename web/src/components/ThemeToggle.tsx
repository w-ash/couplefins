import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "@/components/ThemeProvider";
import type { Theme } from "@/lib/theme";

const options: { value: Theme; icon: typeof Sun; label: string }[] = [
  { value: "light", icon: Sun, label: "Light" },
  { value: "system", icon: Monitor, label: "System" },
  { value: "dark", icon: Moon, label: "Dark" },
];

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <fieldset
      className="inline-flex items-center gap-1 rounded-lg border-0 bg-muted p-1"
      aria-label="Color theme"
    >
      {options.map(({ value, icon: Icon, label }) => (
        <label
          key={value}
          className={`cursor-pointer rounded-md p-1.5 transition-colors ${
            theme === value
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <input
            type="radio"
            name="theme"
            value={value}
            checked={theme === value}
            onChange={() => setTheme(value)}
            className="sr-only"
          />
          <Icon className="size-4" aria-label={label} />
        </label>
      ))}
    </fieldset>
  );
}
