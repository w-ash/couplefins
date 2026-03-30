import { User } from "lucide-react";
import { NavLink } from "react-router";
import { SECONDARY_ROUTES } from "@/lib/navigation";
import { BottomSheet } from "./BottomSheet";
import { LoggedInUser } from "./LoggedInUser";

const sheetLinkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
    isActive
      ? "bg-accent font-medium text-accent-foreground"
      : "text-foreground hover:bg-muted"
  }`;

export function MoreSheet({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  return (
    <BottomSheet open={open} onClose={onClose}>
      <div className="space-y-0.5">
        {SECONDARY_ROUTES.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onClose}
            className={sheetLinkClass}
          >
            <Icon className="size-[18px]" />
            {label}
          </NavLink>
        ))}
        <NavLink to="/account" onClick={onClose} className={sheetLinkClass}>
          <User className="size-[18px]" />
          Account
        </NavLink>
      </div>

      {/* Logged-in user + logout */}
      <div className="mt-3 border-t border-border px-1 pt-3">
        <LoggedInUser />
      </div>
    </BottomSheet>
  );
}
