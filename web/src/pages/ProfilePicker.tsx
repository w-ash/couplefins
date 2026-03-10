import { Heart } from "lucide-react";
import { useIdentityStore } from "@/lib/identity";
import { PERSON_ACCENT_COLORS, type Person } from "@/types/person";

interface ProfilePickerProps {
  persons: Person[];
}

export function ProfilePicker({ persons }: ProfilePickerProps) {
  const setCurrentPersonId = useIdentityStore((s) => s.setCurrentPersonId);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-primary-muted">
            <Heart className="size-6 text-primary" />
          </div>
          <h1 className="font-semibold text-2xl text-foreground">
            Who are you?
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Select your profile to continue
          </p>
        </div>

        <div className="grid gap-4">
          {persons.map((person, index) => (
            <button
              key={person.id}
              type="button"
              onClick={() => setCurrentPersonId(person.id)}
              className="group flex items-center gap-4 rounded-xl border border-border bg-card p-6 shadow-sm transition-all duration-150 hover:border-primary hover:shadow-md"
            >
              <div
                className={`flex size-12 shrink-0 items-center justify-center rounded-full font-semibold text-lg ${PERSON_ACCENT_COLORS[index % PERSON_ACCENT_COLORS.length]}`}
              >
                {person.name.charAt(0).toUpperCase()}
              </div>
              <span className="font-semibold text-lg text-foreground">
                {person.name}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
