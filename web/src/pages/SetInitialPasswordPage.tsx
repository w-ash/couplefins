import { Heart, KeyRound } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useSetInitialPassword } from "@/api/generated/auth/auth";
import type { AuthPersonResponse } from "@/api/generated/model";
import { Button } from "@/components/Button";
import { InlineError } from "@/components/InlineError";
import { PersonPicker, SelectedPersonBadge } from "@/components/PersonPicker";
import { useIdentityStore } from "@/lib/identity";
import { baseInputClass, inputErrorClass } from "@/lib/input-styles";
import { getPasswordErrors, MIN_PASSWORD_LENGTH } from "@/lib/password";

export function SetInitialPasswordPage({
  persons,
  onSuccess,
}: {
  persons: AuthPersonResponse[];
  onSuccess: () => void;
}) {
  const needsPassword = persons.filter((p) => !p.has_password);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const passwordRef = useRef<HTMLInputElement>(null);

  const mutation = useSetInitialPassword({
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
    if (!selectedName || !password || password !== confirmPassword) return;
    mutation.mutate({ data: { name: selectedName, new_password: password } });
  }

  function handleBack() {
    setSelectedName(null);
    setPassword("");
    setConfirmPassword("");
    mutation.reset();
  }

  const { tooShort, mismatch, isValid } = getPasswordErrors(
    password,
    confirmPassword,
  );
  const canSubmit = isValid && !mutation.isPending;

  const selectedIndex = persons.findIndex((p) => p.name === selectedName);

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-md px-6 py-24">
        <div className="mb-8 text-center">
          <div className="mb-4 inline-flex items-center justify-center rounded-full bg-primary-muted p-3">
            <Heart className="size-6 text-primary" />
          </div>
          <h1 className="font-semibold text-2xl text-foreground">
            Set Your Password
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {selectedName
              ? `Create a password for ${selectedName}`
              : "Choose your name to set a password"}
          </p>
        </div>

        {!selectedName ? (
          <PersonPicker persons={needsPassword} onSelect={setSelectedName} />
        ) : (
          <form onSubmit={handleSubmit} className="step-enter space-y-5">
            <SelectedPersonBadge name={selectedName} index={selectedIndex} />

            <div>
              <label
                htmlFor="new-password"
                className="mb-1.5 flex items-center gap-1.5 font-medium text-sm text-secondary-foreground"
              >
                <KeyRound className="size-4" />
                Password
              </label>
              <input
                ref={passwordRef}
                id="new-password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={mutation.isPending}
                className={`w-full ${baseInputClass} ${tooShort ? inputErrorClass : ""}`}
              />
              {tooShort && (
                <p className="mt-1 text-xs text-muted-foreground">
                  At least {MIN_PASSWORD_LENGTH} characters
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="confirm-password"
                className="mb-1.5 block font-medium text-sm text-secondary-foreground"
              >
                Confirm password
              </label>
              <input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={mutation.isPending}
                className={`w-full ${baseInputClass} ${mismatch ? inputErrorClass : ""}`}
              />
              {mismatch && (
                <p className="mt-1 text-xs text-negative">
                  Passwords don't match
                </p>
              )}
            </div>

            <div aria-live="polite" aria-atomic="true">
              {mutation.error && (
                <InlineError>
                  {mutation.error instanceof Error
                    ? mutation.error.message
                    : "Failed to set password"}
                </InlineError>
              )}
            </div>

            <Button
              type="submit"
              disabled={!canSubmit}
              loading={mutation.isPending}
              loadingText="Setting password..."
              fullWidth
            >
              Set Password
            </Button>

            {needsPassword.length > 1 && (
              <button
                type="button"
                onClick={handleBack}
                className="w-full text-center text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                Not {selectedName}?
              </button>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
