import { type FormEvent, useState } from "react";
import {
  useChangePassword,
  useResetPartnerPassword,
} from "@/api/generated/auth/auth";
import { useGetPersons } from "@/api/generated/persons/persons";
import { useIdentityStore } from "@/lib/identity";
import { baseInputClass, inputErrorClass } from "@/lib/input-styles";
import { getPasswordErrors, MIN_PASSWORD_LENGTH } from "@/lib/password";
import { Button } from "./Button";
import { InlineError } from "./InlineError";

function ChangeMyPassword() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [success, setSuccess] = useState(false);

  const mutation = useChangePassword({
    mutation: {
      onSuccess: () => {
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
        setSuccess(true);
      },
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSuccess(false);
    if (!canSubmit) return;
    mutation.mutate({
      data: { current_password: currentPassword, new_password: newPassword },
    });
  }

  const { tooShort, mismatch, isValid } = getPasswordErrors(
    newPassword,
    confirmPassword,
  );
  const canSubmit = currentPassword && isValid && !mutation.isPending;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label
          htmlFor="current-pw"
          className="mb-1.5 block text-sm text-secondary-foreground"
        >
          Current password
        </label>
        <input
          id="current-pw"
          type="password"
          autoComplete="current-password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          disabled={mutation.isPending}
          className={`w-full ${baseInputClass}`}
        />
      </div>
      <div>
        <label
          htmlFor="new-pw"
          className="mb-1.5 block text-sm text-secondary-foreground"
        >
          New password
        </label>
        <input
          id="new-pw"
          type="password"
          autoComplete="new-password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
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
          htmlFor="confirm-new-pw"
          className="mb-1.5 block text-sm text-secondary-foreground"
        >
          Confirm new password
        </label>
        <input
          id="confirm-new-pw"
          type="password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          disabled={mutation.isPending}
          className={`w-full ${baseInputClass} ${mismatch ? inputErrorClass : ""}`}
        />
        {mismatch && (
          <p className="mt-1 text-xs text-negative">Passwords don't match</p>
        )}
      </div>
      <div aria-live="polite" aria-atomic="true">
        {mutation.error && (
          <InlineError>
            {mutation.error instanceof Error
              ? mutation.error.message
              : "Failed to change password"}
          </InlineError>
        )}
        {success && <p className="text-sm text-positive">Password changed</p>}
      </div>
      <Button
        type="submit"
        size="sm"
        disabled={!canSubmit}
        loading={mutation.isPending}
        loadingText="Changing..."
      >
        Change Password
      </Button>
    </form>
  );
}

function ResetPartnerPassword() {
  const currentPersonId = useIdentityStore((s) => s.currentPersonId);
  const { data: personsResponse } = useGetPersons();
  const persons = personsResponse?.data;

  const partner = persons?.find((p) => p.id !== currentPersonId);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [success, setSuccess] = useState(false);

  const mutation = useResetPartnerPassword({
    mutation: {
      onSuccess: () => {
        setNewPassword("");
        setConfirmPassword("");
        setSuccess(true);
      },
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSuccess(false);
    if (!canSubmit) return;
    mutation.mutate({ data: { new_password: newPassword } });
  }

  const { tooShort, mismatch, isValid } = getPasswordErrors(
    newPassword,
    confirmPassword,
  );
  const canSubmit = isValid && !mutation.isPending;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Reset {partner?.name ?? "your partner"}'s password. They'll need the new
        password to log in.
      </p>
      <div>
        <label
          htmlFor="partner-new-pw"
          className="mb-1.5 block text-sm text-secondary-foreground"
        >
          New password for {partner?.name ?? "partner"}
        </label>
        <input
          id="partner-new-pw"
          type="password"
          autoComplete="new-password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
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
          htmlFor="partner-confirm-pw"
          className="mb-1.5 block text-sm text-secondary-foreground"
        >
          Confirm password
        </label>
        <input
          id="partner-confirm-pw"
          type="password"
          autoComplete="new-password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          disabled={mutation.isPending}
          className={`w-full ${baseInputClass} ${mismatch ? inputErrorClass : ""}`}
        />
        {mismatch && (
          <p className="mt-1 text-xs text-negative">Passwords don't match</p>
        )}
      </div>
      <div aria-live="polite" aria-atomic="true">
        {mutation.error && (
          <InlineError>
            {mutation.error instanceof Error
              ? mutation.error.message
              : "Failed to reset password"}
          </InlineError>
        )}
        {success && (
          <p className="text-sm text-positive">
            {partner?.name ?? "Partner"}'s password has been reset
          </p>
        )}
      </div>
      <Button
        type="submit"
        size="sm"
        disabled={!canSubmit}
        loading={mutation.isPending}
        loadingText="Resetting..."
      >
        Reset Password
      </Button>
    </form>
  );
}

export function AccountSettings() {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-3 font-medium text-sm text-foreground">
          Change my password
        </h3>
        <ChangeMyPassword />
      </div>

      <hr className="border-border" />

      <div>
        <h3 className="mb-3 font-medium text-sm text-foreground">
          Reset partner's password
        </h3>
        <ResetPartnerPassword />
      </div>
    </div>
  );
}
