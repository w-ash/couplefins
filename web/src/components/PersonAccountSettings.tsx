import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/InlineError";
import { useTemporary } from "@/hooks/useTemporary";
import { baseInputClass } from "@/lib/input-styles";
import {
  fetchPersons,
  PERSONS_QUERY_KEY,
  type Person,
  updatePerson,
} from "@/types/person";

function PersonAccountRow({ person }: { person: Person }) {
  const [value, setValue] = useState(person.adjustment_account);
  const [saved, setSaved] = useTemporary(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    setValue(person.adjustment_account);
  }, [person.adjustment_account]);

  const mutation = useMutation({
    mutationFn: (account: string) =>
      updatePerson(person.id, { adjustment_account: account }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PERSONS_QUERY_KEY });
      setSaved(true);
    },
  });

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const trimmed = value.trim();
      if (!trimmed || trimmed === person.adjustment_account) return;
      mutation.mutate(trimmed);
    },
    [value, person.adjustment_account, mutation],
  );

  const isDirty =
    value.trim() !== "" && value.trim() !== person.adjustment_account;

  return (
    <form onSubmit={handleSubmit} className="flex items-start gap-3">
      <div className="min-w-0 flex-1">
        <label
          htmlFor={`adj-account-${person.id}`}
          className="mb-1 block text-sm font-medium text-foreground"
        >
          {person.name}
        </label>
        <input
          id={`adj-account-${person.id}`}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="e.g. Shared Expense Adjustments"
          className={`w-full ${baseInputClass} placeholder:text-muted-foreground`}
        />
        {mutation.error && (
          <div className="mt-1">
            <InlineError>{mutation.error.message}</InlineError>
          </div>
        )}
      </div>
      <div className="pt-6">
        {saved ? (
          <span className="inline-flex items-center gap-1 text-sm text-positive">
            <Check className="size-4" />
            Saved
          </span>
        ) : (
          <Button
            type="submit"
            variant="secondary"
            size="sm"
            disabled={!isDirty}
            loading={mutation.isPending}
            loadingText="Saving"
          >
            Save Profile
          </Button>
        )}
      </div>
    </form>
  );
}

export function PersonAccountSettings() {
  const personsQuery = useQuery({
    queryKey: PERSONS_QUERY_KEY,
    queryFn: fetchPersons,
  });

  if (personsQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading profiles...</p>;
  }

  if (personsQuery.isError) {
    return <InlineError>Failed to load profiles.</InlineError>;
  }

  const persons = personsQuery.data ?? [];

  if (persons.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No profiles set up yet. Complete setup first.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Set the Monarch account name where each person imports adjustment
        transactions. Create this as a manual account in Monarch first.
      </p>
      {persons.map((person) => (
        <PersonAccountRow key={person.id} person={person} />
      ))}
    </div>
  );
}
