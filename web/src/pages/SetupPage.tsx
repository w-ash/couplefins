import { useQueryClient } from "@tanstack/react-query";
import { Heart, KeyRound, UserPlus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { getListAuthPersonsQueryKey } from "@/api/generated/auth/auth";
import { useSetupCouple } from "@/api/generated/persons/persons";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { InlineError } from "@/components/InlineError";
import { PasswordInput } from "@/components/PasswordInput";
import { ThemeToggle } from "@/components/ThemeToggle";
import { baseInputClass } from "@/lib/input-styles";
import { getPasswordErrors, MIN_PASSWORD_LENGTH } from "@/lib/password";

export function SetupPage() {
  const queryClient = useQueryClient();
  const [name1, setName1] = useState("");
  const [name2, setName2] = useState("");
  const [password1, setPassword1] = useState("");
  const [confirm1, setConfirm1] = useState("");
  const [password2, setPassword2] = useState("");
  const [confirm2, setConfirm2] = useState("");

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

  const pw1 = getPasswordErrors(password1, confirm1);
  const pw2 = getPasswordErrors(password2, confirm2);
  const canSubmit = name1.trim() && name2.trim() && pw1.isValid && pw2.isValid;

  return (
    <div className="min-h-screen bg-background">
      <div className="flex justify-end px-6 pt-4">
        <ThemeToggle />
      </div>
      <div className="mx-auto max-w-md px-6 py-12">
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
              className={`w-full ${baseInputClass}`}
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
            <PasswordInput
              id="password1"
              value={password1}
              onChange={setPassword1}
              disabled={mutation.isPending}
              hasError={pw1.tooShort}
            />
            {pw1.tooShort && (
              <p className="mt-1 text-xs text-muted-foreground">
                At least {MIN_PASSWORD_LENGTH} characters
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="confirm1"
              className="mb-1.5 block font-medium text-sm text-secondary-foreground"
            >
              Confirm password
            </label>
            <PasswordInput
              id="confirm1"
              value={confirm1}
              onChange={setConfirm1}
              disabled={mutation.isPending}
              hasError={pw1.mismatch}
            />
            {pw1.mismatch && (
              <p className="mt-1 text-xs text-negative">
                Passwords don't match
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
              className={`w-full ${baseInputClass}`}
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
            <PasswordInput
              id="password2"
              value={password2}
              onChange={setPassword2}
              disabled={mutation.isPending}
              hasError={pw2.tooShort}
            />
            {pw2.tooShort && (
              <p className="mt-1 text-xs text-muted-foreground">
                At least {MIN_PASSWORD_LENGTH} characters
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="confirm2"
              className="mb-1.5 block font-medium text-sm text-secondary-foreground"
            >
              Confirm password
            </label>
            <PasswordInput
              id="confirm2"
              value={confirm2}
              onChange={setConfirm2}
              disabled={mutation.isPending}
              hasError={pw2.mismatch}
            />
            {pw2.mismatch && (
              <p className="mt-1 text-xs text-negative">
                Passwords don't match
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
