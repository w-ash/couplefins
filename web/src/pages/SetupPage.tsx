import { useQueryClient } from "@tanstack/react-query";
import { Heart, UserPlus } from "lucide-react";
import { type FormEvent, useState } from "react";
import {
  getGetPersonsQueryKey,
  useSetupCouple,
} from "@/api/generated/persons/persons";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/InlineError";
import { baseInputClass } from "@/lib/input-styles";

export function SetupPage() {
  const queryClient = useQueryClient();
  const [name1, setName1] = useState("");
  const [name2, setName2] = useState("");

  const mutation = useSetupCouple({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetPersonsQueryKey() });
      },
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name1.trim() || !name2.trim()) return;
    mutation.mutate({ data: { name1: name1.trim(), name2: name2.trim() } });
  }

  const namesMatch =
    name1.trim() !== "" &&
    name1.trim().toLowerCase() === name2.trim().toLowerCase();

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-md px-6 py-24">
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex items-center justify-center rounded-full bg-primary-muted p-3">
            <Heart className="size-6 text-primary" />
          </div>
          <h1 className="font-semibold text-2xl text-foreground">
            Welcome to CoupleFins
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Enter both names to get started with shared finance tracking.
          </p>
        </div>

        <Card as="form" onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label
              htmlFor="person1"
              className="mb-1.5 flex items-center gap-1.5 font-medium text-sm text-secondary-foreground"
            >
              <UserPlus className="size-4" />
              Person 1
            </label>
            <input
              id="person1"
              type="text"
              value={name1}
              onChange={(e) => setName1(e.target.value)}
              placeholder="e.g. Alice"
              required
              disabled={mutation.isPending}
              aria-invalid={mutation.isError || undefined}
              className={`w-full ${baseInputClass} placeholder:text-placeholder disabled:cursor-not-allowed disabled:opacity-50`}
            />
          </div>

          <div>
            <label
              htmlFor="person2"
              className="mb-1.5 flex items-center gap-1.5 font-medium text-sm text-secondary-foreground"
            >
              <UserPlus className="size-4" />
              Person 2
            </label>
            <input
              id="person2"
              type="text"
              value={name2}
              onChange={(e) => setName2(e.target.value)}
              placeholder="e.g. Bob"
              required
              disabled={mutation.isPending}
              aria-invalid={mutation.isError || undefined}
              className={`w-full ${baseInputClass} placeholder:text-placeholder disabled:cursor-not-allowed disabled:opacity-50`}
            />
          </div>

          <div aria-live="polite" aria-atomic="true">
            {namesMatch && (
              <p role="alert" className="text-sm text-warning">
                Both names are the same — are you sure?
              </p>
            )}
            {mutation.error && (
              <InlineError>
                {mutation.error instanceof Error
                  ? mutation.error.message
                  : "Setup failed"}
              </InlineError>
            )}
          </div>

          <Button
            type="submit"
            disabled={!name1.trim() || !name2.trim()}
            loading={mutation.isPending}
            loadingText="Setting up..."
            fullWidth
          >
            Get Started
          </Button>
        </Card>
      </div>
    </div>
  );
}
