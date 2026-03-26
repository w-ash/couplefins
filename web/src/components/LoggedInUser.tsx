import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { useLogout } from "@/api/generated/auth/auth";
import { useGetPersons } from "@/api/generated/persons/persons";
import { useIdentityStore } from "@/lib/identity";
import { usePersonMaps } from "@/lib/persons";

export function LoggedInUser({
  compact,
}: {
  /** Tighter spacing for sidebar (desktop). Omit for touch-friendly sizing (mobile). */
  compact?: boolean;
}) {
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const currentPersonName = useIdentityStore((s) => s.currentPersonName);
  const { data: personsResponse } = useGetPersons();
  const { getPersonColor } = usePersonMaps(personsResponse?.data);
  const queryClient = useQueryClient();

  const logoutMutation = useLogout({
    mutation: {
      onSuccess: () => {
        useIdentityStore.getState().clearIdentity();
        queryClient.clear();
      },
    },
  });

  if (!currentPersonName) return null;

  return (
    <div className={`flex items-center gap-2 ${compact ? "" : "px-3 py-1"}`}>
      <div
        className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${getPersonColor(currentPersonId ?? "")}`}
      >
        {currentPersonName.charAt(0).toUpperCase()}
      </div>
      <span className="flex-1 truncate text-sm font-medium text-foreground">
        {currentPersonName}
      </span>
      <button
        type="button"
        onClick={() => logoutMutation.mutate()}
        disabled={logoutMutation.isPending}
        aria-label="Log out"
        className={`shrink-0 rounded-md text-muted-foreground transition-colors hover:text-foreground ${compact ? "p-1" : "p-1.5"} disabled:opacity-50`}
      >
        <LogOut className="size-4" />
      </button>
    </div>
  );
}
