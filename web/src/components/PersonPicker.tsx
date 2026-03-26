import type { AuthPersonResponse } from "@/api/generated/model";
import { PERSON_ACCENT_COLORS } from "@/types/person";

export function PersonPicker({
  persons,
  onSelect,
}: {
  persons: AuthPersonResponse[];
  onSelect: (name: string) => void;
}) {
  return (
    <fieldset
      aria-label="Choose your profile"
      className="step-enter grid gap-4 border-none p-0"
    >
      {persons.map((person, index) => (
        <button
          key={person.name}
          type="button"
          onClick={() => onSelect(person.name)}
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
    </fieldset>
  );
}

export function SelectedPersonBadge({
  name,
  index,
}: {
  name: string;
  index: number;
}) {
  return (
    <div className="flex items-center gap-4 rounded-xl border border-border bg-card p-5 shadow-sm">
      <div
        className={`flex size-10 shrink-0 items-center justify-center rounded-full font-semibold ${PERSON_ACCENT_COLORS[index % PERSON_ACCENT_COLORS.length]}`}
      >
        {name.charAt(0).toUpperCase()}
      </div>
      <span className="font-medium text-foreground">{name}</span>
    </div>
  );
}
