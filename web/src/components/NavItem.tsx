import type { LucideIcon } from "lucide-react";
import { NavLink } from "react-router";

interface NavItemProps {
  to: string;
  label: string;
  icon: LucideIcon;
  disabled?: boolean;
}

export function NavItem({ to, label, icon: Icon, disabled }: NavItemProps) {
  if (disabled) {
    return (
      <span
        aria-disabled="true"
        title="Coming soon"
        className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground/50"
      >
        <Icon className="size-[18px]" />
        {label}
      </span>
    );
  }

  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-150 ${
          isActive
            ? "border-l-2 border-primary bg-accent font-medium text-accent-foreground"
            : "text-muted-foreground hover:bg-muted hover:text-foreground"
        }`
      }
    >
      <Icon className="size-[18px]" />
      {label}
    </NavLink>
  );
}
