import { Settings } from "lucide-react";
import { Card } from "@/components/Card";
import { CategoryMappingEditor } from "@/components/CategoryMappingEditor";
import { PageHeader } from "@/components/PageHeader";
import { PersonAccountSettings } from "@/components/PersonAccountSettings";
import { ThemeToggle } from "@/components/ThemeToggle";
import { PAGE_PADDING } from "@/lib/layout";

export function SettingsPage() {
  return (
    <div className={`mx-auto max-w-3xl ${PAGE_PADDING}`}>
      <PageHeader icon={<Settings className="size-6" />} title="Settings" />

      <div className="space-y-6">
        {/* Appearance */}
        <Card as="section" aria-labelledby="settings-appearance">
          <h2
            id="settings-appearance"
            className="mb-4 font-medium text-lg text-foreground"
          >
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
        </Card>

        {/* Category Mappings */}
        <Card as="section" aria-labelledby="settings-category-mappings">
          <h2
            id="settings-category-mappings"
            className="mb-4 font-medium text-lg text-foreground"
          >
            Category Groups
          </h2>
          <CategoryMappingEditor />
        </Card>

        {/* People */}
        <Card as="section" aria-labelledby="settings-people">
          <h2
            id="settings-people"
            className="mb-4 font-medium text-lg text-foreground"
          >
            People
          </h2>
          <PersonAccountSettings />
        </Card>
      </div>
    </div>
  );
}
