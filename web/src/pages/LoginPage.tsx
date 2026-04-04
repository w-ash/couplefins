import { type FormEvent, useEffect, useRef, useState } from "react";
import { useLogin } from "@/api/generated/auth/auth";
import type { AuthPersonResponse } from "@/api/generated/model";
import { Button } from "@/components/Button";
import { CoupleFinsLogo } from "@/components/CoupleFinsLogo";
import { InlineError } from "@/components/InlineError";
import { PasswordInput } from "@/components/PasswordInput";
import { PersonPicker, SelectedPersonBadge } from "@/components/PersonPicker";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useIdentityStore } from "@/lib/identity";

export function LoginPage({
  persons,
  onSuccess,
}: {
  persons: AuthPersonResponse[];
  onSuccess: () => void;
}) {
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const passwordRef = useRef<HTMLInputElement>(null);

  const loginMutation = useLogin({
    mutation: {
      onSuccess: (response) => {
        const person = response.data as { id: string; name: string };
        useIdentityStore.getState().setFromAuthResponse(person);
        onSuccess();
      },
    },
  });

  useEffect(() => {
    if (selectedName) {
      passwordRef.current?.focus();
    }
  }, [selectedName]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selectedName || !password) return;
    loginMutation.mutate({ data: { name: selectedName, password } });
  }

  function handleBack() {
    setSelectedName(null);
    setPassword("");
    loginMutation.reset();
  }

  const selectedIndex = persons.findIndex((p) => p.name === selectedName);

  return (
    <div className="min-h-screen bg-background">
      <div className="flex justify-end px-6 pt-4">
        <ThemeToggle />
      </div>
      <div className="mx-auto max-w-md px-6 py-12">
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex items-center justify-center rounded-full bg-primary-muted p-3">
            <CoupleFinsLogo className="size-6 text-primary" />
          </div>
          <h1 className="font-semibold text-2xl text-foreground">
            {selectedName ? `Log in as ${selectedName}` : "Welcome back"}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {selectedName
              ? "Enter your password to continue"
              : "Choose your name to log in"}
          </p>
        </div>

        {!selectedName ? (
          <PersonPicker persons={persons} onSelect={setSelectedName} />
        ) : (
          <form onSubmit={handleSubmit} className="step-enter space-y-5">
            <SelectedPersonBadge name={selectedName} index={selectedIndex} />

            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block font-medium text-sm text-secondary-foreground"
              >
                Password
              </label>
              <PasswordInput
                ref={passwordRef}
                id="password"
                autoComplete="current-password"
                value={password}
                onChange={setPassword}
                disabled={loginMutation.isPending}
              />
            </div>

            <div aria-live="polite" aria-atomic="true">
              {loginMutation.error && (
                <InlineError>
                  {loginMutation.error instanceof Error
                    ? loginMutation.error.message
                    : "Login failed"}
                </InlineError>
              )}
            </div>

            <Button
              type="submit"
              disabled={!password}
              loading={loginMutation.isPending}
              loadingText="Logging in..."
              fullWidth
            >
              Log In
            </Button>

            <button
              type="button"
              onClick={handleBack}
              className="w-full text-center text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Not {selectedName}?
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
