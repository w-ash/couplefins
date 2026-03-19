import type { PersonResponse } from "@/api/generated/model";
import { getPersonAccentColor } from "@/types/person";

export function PersonSwitcher({
  persons,
  currentPersonId,
  onSwitch,
  compact,
}: {
  persons: PersonResponse[];
  currentPersonId: string;
  onSwitch: (id: string) => void;
  /** Tighter spacing for sidebar (desktop). Omit for touch-friendly sizing (mobile). */
  compact?: boolean;
}) {
  return (
    <>
      {persons.map((person, index) => {
        const isActive = person.id === currentPersonId;
        return (
          <button
            key={person.id}
            type="button"
            aria-pressed={isActive}
            aria-label={
              isActive ? `${person.name} (active)` : `Switch to ${person.name}`
            }
            onClick={() => {
              if (!isActive) onSwitch(person.id);
            }}
            className={`flex w-full items-center gap-3 rounded-lg text-sm transition-colors ${
              compact ? "px-2 py-1.5 duration-150" : "px-3 py-2.5"
            } ${
              isActive
                ? "bg-accent font-semibold text-accent-foreground"
                : compact
                  ? "cursor-pointer text-muted-foreground hover:bg-muted hover:text-foreground"
                  : "text-foreground hover:bg-muted"
            }`}
          >
            <div
              className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${getPersonAccentColor(index)}`}
            >
              {person.name.charAt(0).toUpperCase()}
            </div>
            {person.name}
          </button>
        );
      })}
    </>
  );
}
