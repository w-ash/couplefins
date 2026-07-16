import { Check, Copy, Loader2 } from "lucide-react";
import { memo, useCallback } from "react";
import { Streamdown } from "streamdown";
import "streamdown/styles.css";
import { useCopyFeedback } from "@/hooks/useCopyFeedback";
import type {
  ChatMessage as ChatMessageType,
  ConfirmationState,
} from "@/lib/chat";
import { cn } from "@/lib/cn";
import { stripUserData } from "@/lib/format";
import { CodeExecutionCard } from "./CodeExecutionCard";
import { ToolCallIndicator } from "./ToolCallIndicator";
import { ToolResultCard } from "./ToolResultCard";

const markdownComponents = {
  p: ({ children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="mb-2 text-sm leading-relaxed last:mb-0" {...props}>
      {children}
    </p>
  ),
  h1: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h1 className="mb-2 mt-4 text-base font-medium first:mt-0" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className="mb-2 mt-3 text-sm font-medium first:mt-0" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="mb-1.5 mt-2.5 text-sm font-medium first:mt-0" {...props}>
      {children}
    </h3>
  ),
  ul: ({ children, ...props }: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="mb-2 list-disc pl-5 last:mb-0" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }: React.OlHTMLAttributes<HTMLOListElement>) => (
    <ol className="mb-2 list-decimal pl-5 last:mb-0" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }: React.LiHTMLAttributes<HTMLLIElement>) => (
    <li className="mb-0.5 text-sm leading-relaxed" {...props}>
      {children}
    </li>
  ),
  blockquote: ({
    children,
    ...props
  }: React.BlockquoteHTMLAttributes<HTMLQuoteElement>) => (
    <blockquote
      className="mb-2 border-l-2 border-primary/30 pl-3 italic last:mb-0"
      {...props}
    >
      {children}
    </blockquote>
  ),
  pre: ({ children, ...props }: React.HTMLAttributes<HTMLPreElement>) => (
    <pre
      className="mb-2 overflow-x-auto rounded-lg bg-background p-3 font-mono text-xs leading-normal last:mb-0"
      {...props}
    >
      {children}
    </pre>
  ),
  code: ({
    children,
    className,
    ...props
  }: React.HTMLAttributes<HTMLElement>) => {
    const isInline = !className;
    if (isInline) {
      return (
        <code
          className="rounded bg-background px-1 py-0.5 font-mono text-[0.85em]"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  strong: ({ children, ...props }: React.HTMLAttributes<HTMLElement>) => (
    <strong className="font-medium" {...props}>
      {children}
    </strong>
  ),
  table: ({
    children,
    ...props
  }: React.TableHTMLAttributes<HTMLTableElement>) => (
    <table className="mb-2 w-full text-sm last:mb-0" {...props}>
      {children}
    </table>
  ),
  tr: ({ children, ...props }: React.HTMLAttributes<HTMLTableRowElement>) => (
    <tr className="border-b border-border text-left" {...props}>
      {children}
    </tr>
  ),
  th: ({
    children,
    ...props
  }: React.ThHTMLAttributes<HTMLTableCellElement>) => (
    <th
      className="py-1 pr-3 text-xs font-medium text-muted-foreground"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({
    children,
    ...props
  }: React.TdHTMLAttributes<HTMLTableCellElement>) => (
    <td className="py-1 pr-3 tabular-nums" {...props}>
      {children}
    </td>
  ),
};

function CopyButton({ content }: { content: string }) {
  const { copied, markCopied } = useCopyFeedback();

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(content);
    markCopied();
  }, [content, markCopied]);

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? "Copied" : "Copy"}
      aria-label={copied ? "Copied" : "Copy message"}
      className={cn(
        "flex size-7 items-center justify-center rounded-md text-muted-foreground transition-opacity hover:text-foreground",
        "max-md:size-11",
        "opacity-0 focus-visible:opacity-100 group-hover:opacity-100 max-md:opacity-100",
      )}
    >
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </button>
  );
}

// Memoized: the store's updateMessage preserves identity of untouched
// messages, so streaming one message no longer re-renders the whole list.
export const ChatMessage = memo(function ChatMessage({
  message,
  confirmationStates,
  onConfirm,
  onCancel,
}: {
  message: ChatMessageType;
  confirmationStates?: Record<string, ConfirmationState>;
  onConfirm?: (actionId: string) => void;
  onCancel?: (actionId: string) => void;
}) {
  const isUser = message.role === "user";
  // The model sees user_data tags in its tool results and may echo them
  // into prose — strip them before rendering (and copying) assistant text.
  const content = isUser ? message.content : stripUserData(message.content);
  const showCopy =
    !isUser && !message.isStreaming && !message.error && !!message.content;

  return (
    <div
      className={cn(
        "group flex flex-col gap-1",
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
        {content &&
          (isUser ? (
            <p className="whitespace-pre-wrap">{content}</p>
          ) : (
            <Streamdown
              isAnimating={message.isStreaming}
              animated={false}
              components={markdownComponents}
            >
              {content}
            </Streamdown>
          ))}
        {message.error && (
          <p className="text-destructive-muted-foreground">
            {message.error.message}
          </p>
        )}
      </div>
      {message.codeExecutions && message.codeExecutions.length > 0 && (
        <div className="flex w-full max-w-[85%] flex-col gap-2 px-1">
          {message.codeExecutions.map((ce) => (
            <CodeExecutionCard key={ce.id} execution={ce} />
          ))}
        </div>
      )}
      {message.toolCalls && message.toolCalls.length > 0 && (
        <div className="flex max-w-[85%] flex-col gap-2 px-1">
          <div className="flex flex-wrap gap-1.5">
            {message.toolCalls.map((tc) => (
              <ToolCallIndicator key={tc.id} toolCall={tc} />
            ))}
          </div>
          {message.toolCalls.map((tc) => {
            const result = tc.result as Record<string, unknown> | undefined;
            const actionId = result?.action_id as string | undefined;
            return (
              <ToolResultCard
                key={`result-${tc.id}`}
                toolCall={tc}
                confirmationState={
                  actionId ? confirmationStates?.[actionId] : undefined
                }
                onConfirm={onConfirm}
                onCancel={onCancel}
              />
            );
          })}
        </div>
      )}
      {showCopy && <CopyButton content={content} />}
    </div>
  );
});
