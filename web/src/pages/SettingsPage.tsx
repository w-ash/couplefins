import { Settings } from "lucide-react";
import { AccountSettings } from "@/components/AccountSettings";
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
            className="mb-1 font-medium text-lg text-foreground"
          >
            Appearance
          </h2>
          <p className="mb-4 text-xs text-muted-foreground">
            Control how the app looks on your device
          </p>
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

        {/* Account */}
        <Card as="section" aria-labelledby="settings-account">
          <h2
            id="settings-account"
            className="mb-1 font-medium text-lg text-foreground"
          >
            Account
          </h2>
          <p className="mb-4 text-xs text-muted-foreground">
            Manage passwords for you and your partner
          </p>
          <AccountSettings />
        </Card>

        {/* Category Mappings */}
        <Card as="section" aria-labelledby="settings-category-mappings">
          <h2
            id="settings-category-mappings"
            className="mb-1 font-medium text-lg text-foreground"
          >
            Category Groups
          </h2>
          <p className="mb-4 text-xs text-muted-foreground">
            Map Monarch categories to budget groups
          </p>
          <CategoryMappingEditor />
        </Card>

        {/* People */}
        <Card as="section" aria-labelledby="settings-people">
          <h2
            id="settings-people"
            className="mb-1 font-medium text-lg text-foreground"
          >
            People
          </h2>
          <p className="mb-4 text-xs text-muted-foreground">
            Names and Monarch adjustment account names for CSV export
          </p>
          <PersonAccountSettings />
        </Card>
      </div>
    </div>
  );
}
