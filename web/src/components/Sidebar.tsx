import { PRIMARY_ROUTES, SECONDARY_ROUTES } from "@/lib/navigation";
import { CoupleFinsLogo } from "./CoupleFinsLogo";
import { LoggedInUser } from "./LoggedInUser";
import { NavItem } from "./NavItem";

export function Sidebar() {
  return (
    <aside
      aria-label="Main navigation"
      className="flex w-56 shrink-0 flex-col border-r border-border bg-card"
    >
      {/* Wordmark */}
      <div className="flex items-center gap-2 px-5 py-5">
        <CoupleFinsLogo className="h-5 w-auto text-primary" />
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

      {/* Logged-in user + logout */}
      <div className="border-t border-border px-4 py-4">
        <LoggedInUser compact />
      </div>
    </aside>
  );
}
