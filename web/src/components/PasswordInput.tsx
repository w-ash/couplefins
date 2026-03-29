import { Eye, EyeOff } from "lucide-react";
import { type Ref, useState } from "react";
import { baseInputClass, inputErrorClass } from "@/lib/input-styles";

export function PasswordInput({
  id,
  value,
  onChange,
  autoComplete = "new-password",
  disabled,
  hasError,
  ref,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
  disabled?: boolean;
  hasError?: boolean;
  ref?: Ref<HTMLInputElement>;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <input
        ref={ref}
        id={id}
        type={visible ? "text" : "password"}
        autoComplete={autoComplete}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={`w-full pr-10 ${baseInputClass} ${hasError ? inputErrorClass : ""}`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
        aria-controls={id}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
}
