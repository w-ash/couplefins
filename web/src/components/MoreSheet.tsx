import { User } from "lucide-react";
import { NavLink } from "react-router";
import { CHAT_ROUTE, SECONDARY_ROUTES } from "@/lib/navigation";
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
  chatAvailable = false,
}: {
  open: boolean;
  onClose: () => void;
  chatAvailable?: boolean;
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
        {chatAvailable && (
          <NavLink
            to={CHAT_ROUTE.to}
            onClick={onClose}
            className={sheetLinkClass}
          >
            <CHAT_ROUTE.icon className="size-[18px]" />
            {CHAT_ROUTE.label}
          </NavLink>
        )}
        <NavLink to="/account" onClick={onClose} className={sheetLinkClass}>
          <User className="size-[18px]" />
          Account
        </NavLink>
      </div>

      <div className="mt-3 border-t border-border px-1 pt-3">
        <LoggedInUser />
      </div>
    </BottomSheet>
  );
}
