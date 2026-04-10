import { Send, Square } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { cn } from "@/lib/cn";
import { baseInputClass } from "@/lib/input-styles";

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
      el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
    }
  };

  return (
    <div className="flex items-end gap-2 border-t border-border px-4 py-3">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          resize();
        }}
        onKeyDown={handleKeyDown}
        placeholder="Ask about your finances..."
        disabled={isStreaming}
        rows={1}
        className={cn(baseInputClass, "min-h-0 flex-1 resize-none py-2")}
      />
      {isStreaming ? (
        <Button
          variant="secondary"
          size="sm"
          onClick={onStop}
          icon={<Square className="size-3.5" />}
        >
          Stop
        </Button>
      ) : (
        <Button
          size="sm"
          onClick={handleSubmit}
          disabled={!value.trim()}
          icon={<Send className="size-3.5" />}
          aria-label="Send"
        />
      )}
    </div>
  );
}
