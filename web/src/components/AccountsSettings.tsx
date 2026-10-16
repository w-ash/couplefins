import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import type { AccountResponse } from "@/api/generated/model";
import { useGetPersons } from "@/api/generated/persons/persons";
import {
  useGetAccounts,
  useMarkAccountJoint,
  useUnmarkAccountJoint,
} from "@/api/generated/settings/settings";
import { Button } from "@/components/Button";
import { Dialog, DialogFooter, DialogHeader } from "@/components/Dialog";
import { JointPill } from "@/components/GroupKindPill";
import { InlineError } from "@/components/InlineError";
import { PageError, PageLoading } from "@/components/PageStates";
import { PersonBadge } from "@/components/PersonBadge";
import { ACCOUNT_QUERY_KEYS } from "@/hooks/useRealtimeSync";
import { usePersonMaps } from "@/lib/persons";

interface LabelGroup {
  name: string;
  joint: boolean;
  owners: string[];
}

function groupByLabel(accounts: AccountResponse[]): LabelGroup[] {
  const groups = new Map<string, LabelGroup>();
  for (const account of accounts) {
    const group = groups.get(account.name) ?? {
      name: account.name,
      joint: false,
      owners: [],
    };
    if (account.kind === "joint") group.joint = true;
    else if (
      account.owner_person_id &&
      !group.owners.includes(account.owner_person_id)
    )
      group.owners.push(account.owner_person_id);
    groups.set(account.name, group);
  }
  return [...groups.values()].sort((a, b) => a.name.localeCompare(b.name));
}

export function AccountsSettings() {
  const queryClient = useQueryClient();
  const { data: personsResponse } = useGetPersons();
  const { getPersonName, getPersonColor } = usePersonMaps(
    personsResponse?.data,
  );
  const {
    data: accountsResponse,
    isLoading,
    isError,
    refetch,
  } = useGetAccounts();
  const accounts =
    accountsResponse?.status === 200 ? accountsResponse.data.accounts : [];
  const groups = useMemo(() => groupByLabel(accounts), [accounts]);

  const [pending, setPending] = useState<LabelGroup | null>(null);

  function onSuccess() {
    for (const queryKey of ACCOUNT_QUERY_KEYS) {
      queryClient.invalidateQueries({ queryKey });
    }
    setPending(null);
  }

  const markMutation = useMarkAccountJoint({ mutation: { onSuccess } });
  const unmarkMutation = useUnmarkAccountJoint({ mutation: { onSuccess } });
  const mutation = pending?.joint ? unmarkMutation : markMutation;

  function close() {
    setPending(null);
    markMutation.reset();
    unmarkMutation.reset();
  }

  function confirm() {
    if (!pending) return;
    if (pending.joint)
      unmarkMutation.mutate({ label: encodeURIComponent(pending.name) });
    else markMutation.mutate({ data: { label: pending.name } });
  }

  if (isLoading) return <PageLoading label="Loading accounts..." />;
  if (isError) {
    return (
      <PageError
        error={new Error("Failed to load accounts.")}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-3">
      {groups.length === 0 ? (
        <p className="py-2 text-sm text-muted-foreground">
          No accounts yet. They appear after your first upload.
        </p>
      ) : (
        <ul className="space-y-2">
          {groups.map((group) => (
            <li
              key={group.name}
              className="flex items-center justify-between gap-3 rounded-lg border border-border-muted px-4 py-2.5"
            >
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <span className="truncate text-sm font-medium text-foreground">
                  {group.name}
                </span>
                {group.joint ? (
                  <JointPill />
                ) : (
                  group.owners.map((id) => (
                    <PersonBadge
                      key={id}
                      name={getPersonName(id)}
                      accentColor={getPersonColor(id)}
                      size="xs"
                    />
                  ))
                )}
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPending(group)}
                aria-label={`${group.joint ? "Unmark" : "Mark joint"} ${group.name}`}
              >
                {group.joint ? "Unmark" : "Mark joint"}
              </Button>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={pending !== null} onClose={close} size="sm">
        {pending && (
          <>
            <DialogHeader
              title={
                pending.joint
                  ? `Unmark ${pending.name}?`
                  : `Mark ${pending.name} joint?`
              }
              onClose={close}
            />
            <p className="mt-3 text-sm text-muted-foreground">
              {pending.joint
                ? "Existing rows under this label go back to the partner who uploaded them, and return to settlement."
                : "Existing rows under this label move out of settlement and lose their payer, with shares by owner. Duplicate rows both of you imported collapse to one."}
            </p>
            {mutation.isError && (
              <div className="mt-3">
                <InlineError>
                  {mutation.error instanceof Error
                    ? mutation.error.message
                    : "Could not update the account"}
                </InlineError>
              </div>
            )}
            <DialogFooter>
              <Button variant="secondary" onClick={close}>
                Cancel
              </Button>
              <Button onClick={confirm} loading={mutation.isPending}>
                {pending.joint ? "Unmark" : "Mark joint"}
              </Button>
            </DialogFooter>
          </>
        )}
      </Dialog>
    </div>
  );
}
