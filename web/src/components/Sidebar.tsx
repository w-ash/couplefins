import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  Heart,
  LayoutDashboard,
  PieChart,
  Settings,
  Upload,
} from "lucide-react";
import { useIdentityStore } from "@/lib/identity";
import {
  fetchPersons,
  getPersonAccentColor,
  PERSONS_QUERY_KEY,
} from "@/types/person";
import { NavItem } from "./NavItem";

export function Sidebar() {
  const { data: persons } = useQuery({
    queryKey: PERSONS_QUERY_KEY,
    queryFn: fetchPersons,
  });
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
        <NavItem to="/" label="Dashboard" icon={LayoutDashboard} disabled />
        <NavItem
          to="/transactions"
          label="Transactions"
          icon={ArrowLeftRight}
        />
        <NavItem to="/budget" label="Budget" icon={PieChart} disabled />
        <NavItem to="/upload" label="Upload" icon={Upload} />
        <NavItem to="/settings" label="Settings" icon={Settings} />
      </nav>

      {/* Identity toggle */}
      {persons && persons.length >= 2 && (
        <div className="space-y-1 border-t border-border px-4 py-4">
          {persons.map((person, index) => {
            const isActive = person.id === currentPersonId;
            return (
              <button
                key={person.id}
                type="button"
                aria-pressed={isActive}
                aria-label={
                  isActive
                    ? `${person.name} (active)`
                    : `Switch to ${person.name}`
                }
                onClick={() => {
                  if (!isActive) setCurrentPersonId(person.id);
                }}
                className={`flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-sm transition-colors duration-150 ${
                  isActive
                    ? "font-semibold text-foreground"
                    : "cursor-pointer text-muted-foreground hover:text-foreground"
                }`}
              >
                <div
                  className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${getPersonAccentColor(index)}`}
                >
                  {person.name.charAt(0).toUpperCase()}
                </div>
                {person.name}
                {isActive && (
                  <div className="ml-auto size-2 rounded-full bg-primary" />
                )}
              </button>
            );
          })}
        </div>
      )}
    </aside>
  );
}
