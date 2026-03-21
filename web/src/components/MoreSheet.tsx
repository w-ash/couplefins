import { NavLink } from "react-router";
import { useGetPersons } from "@/api/generated/persons/persons";
import { useIdentityStore } from "@/lib/identity";
import { SECONDARY_ROUTES } from "@/lib/navigation";
import { BottomSheet } from "./BottomSheet";
import { PersonSwitcher } from "./PersonSwitcher";

export function MoreSheet({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { data: response } = useGetPersons();
  const persons = response?.data;
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const setCurrentPersonId = useIdentityStore((s) => s.setCurrentPersonId);

  return (
    <BottomSheet open={open} onClose={onClose}>
      <div className="space-y-0.5">
        {SECONDARY_ROUTES.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                isActive
                  ? "bg-accent font-medium text-accent-foreground"
                  : "text-foreground hover:bg-muted"
              }`
            }
          >
            <Icon className="size-[18px]" />
            {label}
          </NavLink>
        ))}
      </div>

      {/* Identity toggle */}
      {persons && persons.length >= 2 && currentPersonId && (
        <div className="mt-3 space-y-0.5 border-t border-border pt-3">
          <p className="mb-1.5 px-3 text-xs font-medium text-muted-foreground">
            Viewing as
          </p>
          <PersonSwitcher
            persons={persons}
            currentPersonId={currentPersonId}
            onSwitch={(id) => {
              setCurrentPersonId(id);
              onClose();
            }}
          />
        </div>
      )}
    </BottomSheet>
  );
}
