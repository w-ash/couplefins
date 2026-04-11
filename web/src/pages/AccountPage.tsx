import { User } from "lucide-react";
import {
  useGetPersons,
  useUpdatePerson,
} from "@/api/generated/persons/persons";
import { AccountSettings } from "@/components/AccountSettings";
import { Card } from "@/components/Card";
import { ChatVoiceSelector } from "@/components/ChatVoiceSelector";
import { PageHeader } from "@/components/PageHeader";
import { PersonAccountSettings } from "@/components/PersonAccountSettings";
import { SectionHeader } from "@/components/SectionHeader";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useIdentityStore } from "@/lib/identity";
import { PAGE_PADDING } from "@/lib/layout";
import type { Theme } from "@/lib/theme";

export function AccountPage() {
  const personId = useIdentityStore((s) => s.currentPersonId);
  const personName = useIdentityStore((s) => s.currentPersonName);
  const updatePerson = useUpdatePerson();
  const { data: persons } = useGetPersons();

  const currentVoice =
    persons?.data?.find((p) => p.id === personId)?.chat_voice ?? "fiona";

  function persistTheme(theme: Theme) {
    if (!personId) return;
    updatePerson.mutate({ personId, data: { theme_preference: theme } });
  }

  function persistVoice(voice: string) {
    if (!personId) return;
    updatePerson.mutate({ personId, data: { chat_voice: voice } });
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
          <SectionHeader
            id="account-appearance"
            title="Appearance"
            description="Control how the app looks on your device"
          />
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

        {/* Chat personality */}
        <Card as="section" aria-labelledby="account-chat-voice">
          <SectionHeader
            id="account-chat-voice"
            title="Chat personality"
            description="Choose the voice for your chat assistant"
          />
          <ChatVoiceSelector
            currentVoice={currentVoice}
            onPersist={persistVoice}
          />
        </Card>

        {/* Security */}
        <Card as="section" aria-labelledby="account-security">
          <SectionHeader
            id="account-security"
            title="Security"
            description="Manage passwords for you and your partner"
          />
          <AccountSettings />
        </Card>

        {/* Export account */}
        <Card as="section" aria-labelledby="account-export">
          <SectionHeader
            id="account-export"
            title="Monarch Export"
            description="Account name used when generating adjustment CSVs for Monarch import"
          />
          <PersonAccountSettings filterToPersonId={personId ?? undefined} />
        </Card>
      </div>
    </div>
  );
}
