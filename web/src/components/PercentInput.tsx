import type { RefObject } from "react";
import { InlineError } from "@/components/InlineError";
import { inputErrorClass, percentInputClass } from "@/lib/input-styles";

interface PercentInputProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  error?: boolean;
  errorMessage?: string;
  placeholder?: string;
  inputRef?: RefObject<HTMLInputElement | null>;
  onKeyDown?: React.KeyboardEventHandler<HTMLInputElement>;
}

export function PercentInput({
  id,
  value,
  onChange,
  disabled,
  error,
  errorMessage = "0\u2013100",
  placeholder,
  inputRef,
  onKeyDown,
}: PercentInputProps) {
  return (
    <>
      <input
        id={id}
        ref={inputRef}
        type="number"
        min={0}
        max={100}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        className={`${percentInputClass} ${error ? inputErrorClass : ""}`}
        disabled={disabled}
        aria-invalid={error || undefined}
      />
      <span>%</span>
      {error && <InlineError>{errorMessage}</InlineError>}
    </>
  );
}
