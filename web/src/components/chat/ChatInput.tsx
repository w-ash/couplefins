import { ArrowUp, Square } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { cn } from "@/lib/cn";

export function ChatInput({
  onSubmit,
  isStreaming,
  onStop,
}: {
  onSubmit: (text: string) => void;
  isStreaming: boolean;
  onStop: () => void;
}) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    onSubmit(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, isStreaming, onSubmit]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const resize = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    }
  };

  const canSend = value.trim().length > 0 && !isStreaming;

  return (
    <div className="px-3 pb-3 pt-2">
      <div
        className={cn(
          "flex items-end gap-2 rounded-2xl border border-input bg-card px-3 py-2 shadow-sm",
          "transition-[border-color,box-shadow] duration-150",
          "focus-within:border-ring focus-within:ring-1 focus-within:ring-ring",
        )}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            resize();
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your finances…"
          disabled={isStreaming}
          rows={1}
          className={cn(
            "flex-1 resize-none self-center bg-transparent py-1.5 text-sm leading-relaxed",
            "text-foreground placeholder:text-placeholder",
            "focus:outline-none disabled:cursor-not-allowed disabled:opacity-50",
          )}
        />
        {isStreaming ? (
          <Button
            variant="secondary"
            size="icon"
            onClick={onStop}
            aria-label="Stop generating"
            title="Stop generating"
            icon={<Square className="size-3.5 fill-current" />}
          />
        ) : (
          <Button
            variant="primary"
            size="icon"
            onClick={handleSubmit}
            disabled={!canSend}
            aria-label="Send message"
            title="Send"
            icon={<ArrowUp className="size-4" />}
          />
        )}
      </div>
    </div>
  );
}
