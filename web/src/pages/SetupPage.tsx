import { useQueryClient } from "@tanstack/react-query";
import { Heart, KeyRound, UserPlus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { getListAuthPersonsQueryKey } from "@/api/generated/auth/auth";
import { useSetupCouple } from "@/api/generated/persons/persons";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/InlineError";
import { baseInputClass } from "@/lib/input-styles";
import { MIN_PASSWORD_LENGTH } from "@/lib/password";

export function SetupPage() {
  const queryClient = useQueryClient();
  const [name1, setName1] = useState("");
  const [name2, setName2] = useState("");
  const [password1, setPassword1] = useState("");
  const [password2, setPassword2] = useState("");

  const mutation = useSetupCouple({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListAuthPersonsQueryKey(),
        });
      },
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name1.trim() || !name2.trim() || !password1 || !password2) return;
    mutation.mutate({
      data: {
        name1: name1.trim(),
        name2: name2.trim(),
        password1,
        password2,
      },
    });
  }

  const namesMatch =
    name1.trim() !== "" &&
    name1.trim().toLowerCase() === name2.trim().toLowerCase();

  const pw1TooShort =
    password1.length > 0 && password1.length < MIN_PASSWORD_LENGTH;
  const pw2TooShort =
    password2.length > 0 && password2.length < MIN_PASSWORD_LENGTH;
  const canSubmit =
    name1.trim() &&
    name2.trim() &&
    password1.length >= MIN_PASSWORD_LENGTH &&
    password2.length >= MIN_PASSWORD_LENGTH;

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
            Enter both names and passwords to get started.
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
              className={`w-full ${baseInputClass} placeholder:text-placeholder disabled:cursor-not-allowed disabled:opacity-50`}
            />
          </div>

          <div>
            <label
              htmlFor="password1"
              className="mb-1.5 flex items-center gap-1.5 font-medium text-sm text-secondary-foreground"
            >
              <KeyRound className="size-4" />
              {name1.trim() ? `${name1.trim()}'s password` : "Password"}
            </label>
            <input
              id="password1"
              type="password"
              autoComplete="new-password"
              value={password1}
              onChange={(e) => setPassword1(e.target.value)}
              disabled={mutation.isPending}
              className={`w-full ${baseInputClass} placeholder:text-placeholder disabled:cursor-not-allowed disabled:opacity-50`}
            />
            {pw1TooShort && (
              <p className="mt-1 text-xs text-muted-foreground">
                At least {MIN_PASSWORD_LENGTH} characters
              </p>
            )}
          </div>

          <hr className="border-border" />

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
              className={`w-full ${baseInputClass} placeholder:text-placeholder disabled:cursor-not-allowed disabled:opacity-50`}
            />
          </div>

          <div>
            <label
              htmlFor="password2"
              className="mb-1.5 flex items-center gap-1.5 font-medium text-sm text-secondary-foreground"
            >
              <KeyRound className="size-4" />
              {name2.trim() ? `${name2.trim()}'s password` : "Password"}
            </label>
            <input
              id="password2"
              type="password"
              autoComplete="new-password"
              value={password2}
              onChange={(e) => setPassword2(e.target.value)}
              disabled={mutation.isPending}
              className={`w-full ${baseInputClass} placeholder:text-placeholder disabled:cursor-not-allowed disabled:opacity-50`}
            />
            {pw2TooShort && (
              <p className="mt-1 text-xs text-muted-foreground">
                At least {MIN_PASSWORD_LENGTH} characters
              </p>
            )}
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
            disabled={!canSubmit}
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
