import { User } from "lucide-react";
import { useUpdatePerson } from "@/api/generated/persons/persons";
import { AccountSettings } from "@/components/AccountSettings";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { PersonAccountSettings } from "@/components/PersonAccountSettings";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useIdentityStore } from "@/lib/identity";
import {
  PAGE_PADDING,
  sectionDescriptionClass,
  sectionHeadingClass,
} from "@/lib/layout";
import type { Theme } from "@/lib/theme";

export function AccountPage() {
  const personId = useIdentityStore((s) => s.currentPersonId);
  const personName = useIdentityStore((s) => s.currentPersonName);
  const updatePerson = useUpdatePerson();

  function persistTheme(theme: Theme) {
    if (!personId) return;
    updatePerson.mutate({ personId, data: { theme_preference: theme } });
  }

  return (
    <div className={`mx-auto max-w-3xl ${PAGE_PADDING}`}>
      <PageHeader
        icon={<User className="size-6" />}
        title={personName ? `${personName}'s Account` : "Account"}
      />

      <div className="space-y-6">
        {/* Appearance */}
        <Card as="section" aria-labelledby="account-appearance">
          <h2 id="account-appearance" className={sectionHeadingClass}>
            Appearance
          </h2>
          <p className={sectionDescriptionClass}>
            Control how the app looks on your device
          </p>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-foreground">Theme</p>
              <p className="text-sm text-muted-foreground">
                Choose light, dark, or match your system
              </p>
            </div>
            <ThemeToggle onPersist={persistTheme} />
          </div>
        </Card>

        {/* Security */}
        <Card as="section" aria-labelledby="account-security">
          <h2 id="account-security" className={sectionHeadingClass}>
            Security
          </h2>
          <p className={sectionDescriptionClass}>
            Manage passwords for you and your partner
          </p>
          <AccountSettings />
        </Card>

        {/* Export account */}
        <Card as="section" aria-labelledby="account-export">
          <h2 id="account-export" className={sectionHeadingClass}>
            Monarch Export
          </h2>
          <p className={sectionDescriptionClass}>
            Account name used when generating adjustment CSVs for Monarch import
          </p>
          <PersonAccountSettings filterToPersonId={personId ?? undefined} />
        </Card>
      </div>
    </div>
  );
}
