import { MoreHorizontal } from "lucide-react";
import { useState } from "react";
import { NavLink } from "react-router";
import { PRIMARY_ROUTES } from "@/lib/navigation";
import { MoreSheet } from "./MoreSheet";

export function BottomNav({
  chatAvailable = false,
}: {
  chatAvailable?: boolean;
}) {
  const [moreOpen, setMoreOpen] = useState(false);

  return (
    <>
      <nav
        aria-label="Mobile navigation"
        className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-card pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        <div className="flex items-stretch">
          {PRIMARY_ROUTES.map(({ to, label, shortLabel, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex flex-1 flex-col items-center gap-0.5 pb-1.5 pt-2 text-[10px] transition-colors ${
                  isActive
                    ? "border-t-2 border-primary font-medium text-primary"
                    : "border-t-2 border-transparent text-muted-foreground"
                }`
              }
            >
              <Icon className="size-5" />
              {shortLabel ?? label}
            </NavLink>
          ))}
          <button
            type="button"
            onClick={() => setMoreOpen(true)}
            className="flex flex-1 flex-col items-center gap-0.5 border-t-2 border-transparent pb-1.5 pt-2 text-[10px] text-muted-foreground transition-colors"
          >
            <MoreHorizontal className="size-5" />
            More
          </button>
        </div>
      </nav>

      <MoreSheet
        open={moreOpen}
        onClose={() => setMoreOpen(false)}
        chatAvailable={chatAvailable}
      />
    </>
  );
}
