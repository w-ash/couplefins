import { Settings } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";

export function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="mb-8 flex items-center gap-2.5 font-semibold text-2xl text-foreground">
        <Settings className="size-6" />
        Settings
      </h1>

      <div className="space-y-6">
        {/* Appearance */}
        <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <h2 className="mb-4 font-medium text-lg text-foreground">
            Appearance
          </h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-foreground">Theme</p>
              <p className="text-sm text-muted-foreground">
                Choose light, dark, or match your system
              </p>
            </div>
            <ThemeToggle />
          </div>
        </section>

        {/* Category Mappings */}
        <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <h2 className="mb-2 font-medium text-lg text-foreground">
            Category Mappings
          </h2>
          <p className="text-sm text-muted-foreground">
            Category group management coming in a future update.
          </p>
        </section>

        {/* People */}
        <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
          <h2 className="mb-2 font-medium text-lg text-foreground">People</h2>
          <p className="text-sm text-muted-foreground">
            Person configuration coming in a future update.
          </p>
        </section>
      </div>
    </div>
  );
}
