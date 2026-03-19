import { Heart } from "lucide-react";
import { useGetPersons } from "@/api/generated/persons/persons";
import { useIdentityStore } from "@/lib/identity";
import { PRIMARY_ROUTES, SECONDARY_ROUTES } from "@/lib/navigation";
import { NavItem } from "./NavItem";
import { PersonSwitcher } from "./PersonSwitcher";

export function Sidebar() {
  const { data: response } = useGetPersons();
  const persons = response?.data;
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const setCurrentPersonId = useIdentityStore((s) => s.setCurrentPersonId);

  return (
    <aside
      aria-label="Main navigation"
      className="flex w-56 shrink-0 flex-col border-r border-border bg-card"
    >
      {/* Wordmark */}
      <div className="flex items-center gap-2 px-5 py-5">
        <Heart className="size-5 text-primary" />
        <span className="font-semibold text-lg text-foreground">
          CoupleFins
        </span>
      </div>

      {/* Navigation */}
      <nav aria-label="App navigation" className="flex-1 space-y-1 px-3 py-4">
        {PRIMARY_ROUTES.map((route) => (
          <NavItem
            key={route.to}
            to={route.to}
            label={route.label}
            icon={route.icon}
          />
        ))}
        {SECONDARY_ROUTES.map((route) => (
          <NavItem
            key={route.to}
            to={route.to}
            label={route.label}
            icon={route.icon}
          />
        ))}
      </nav>

      {/* Identity toggle */}
      {persons && persons.length >= 2 && currentPersonId && (
        <div className="space-y-1 border-t border-border px-4 py-4">
          <PersonSwitcher
            persons={persons}
            currentPersonId={currentPersonId}
            onSwitch={setCurrentPersonId}
            compact
          />
        </div>
      )}
    </aside>
  );
}
