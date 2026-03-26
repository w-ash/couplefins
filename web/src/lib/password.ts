export const MIN_PASSWORD_LENGTH = 8;

export function getPasswordErrors(password: string, confirmPassword?: string) {
  const hasConfirm = confirmPassword !== undefined;
  return {
    tooShort: password.length > 0 && password.length < MIN_PASSWORD_LENGTH,
    mismatch:
      hasConfirm && confirmPassword.length > 0 && password !== confirmPassword,
    isValid:
      password.length >= MIN_PASSWORD_LENGTH &&
      (!hasConfirm || confirmPassword === password),
  };
}
