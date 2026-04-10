import { Loader2 } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "@/lib/chat";
import { cn } from "@/lib/cn";
import { ToolCallIndicator } from "./ToolCallIndicator";

export function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex flex-col gap-1",
        isUser ? "items-end" : "items-start",
      )}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
          isUser
            ? "bg-primary-muted text-foreground"
            : "bg-muted text-foreground",
        )}
      >
        {message.isStreaming && !message.content && (
          <output aria-label="Thinking">
            <Loader2 className="size-4 animate-spin text-muted-foreground" />
          </output>
        )}
        {message.content && (
          <p className="whitespace-pre-wrap">{message.content}</p>
        )}
        {message.error && (
          <p className="text-destructive-muted-foreground">
            {message.error.message}
          </p>
        )}
      </div>
      {message.toolCalls && message.toolCalls.length > 0 && (
        <div className="flex flex-wrap gap-1.5 px-1">
          {message.toolCalls.map((tc) => (
            <ToolCallIndicator key={tc.id} toolCall={tc} />
          ))}
        </div>
      )}
    </div>
  );
}
