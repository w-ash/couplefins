import { X } from "lucide-react";
import { useCallback, useEffect } from "react";
import type { ChatSSECallbacks } from "@/api/chat-sse";
import { sendChatMessage } from "@/api/chat-sse";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";
import { useChatStore } from "@/lib/chat";
import { ChatInput } from "./ChatInput";
import { ChatMessageList } from "./ChatMessageList";
import { SuggestedQuestions } from "./SuggestedQuestions";

const closePanel = () => useChatStore.getState().setPanelOpen(false);

export function ChatPanel({ fullScreen = false }: { fullScreen?: boolean }) {
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const abortController = useChatStore((s) => s.abortController);

  const sendQuestion = useCallback((text: string) => {
    const store = useChatStore.getState();
    if (store.isStreaming) return;

    store.addUserMessage(text);
    const assistantId = store.startAssistantMessage();
    const controller = new AbortController();
    store.setAbortController(controller);

    // Build API messages from conversation history, excluding the
    // empty assistant message we just added and any errored messages
    const apiMessages = useChatStore
      .getState()
      .messages.filter((m) => !m.error && !(m.id === assistantId))
      .map((m) => ({ role: m.role, content: m.content }));

    const callbacks: ChatSSECallbacks = {
      onToken: (t) => useChatStore.getState().appendToken(assistantId, t),
      onToolStart: (_name, id) =>
        useChatStore.getState().addToolCall(assistantId, id, _name),
      onToolResult: (_name, toolUseId, result, isError) => {
        useChatStore
          .getState()
          .setToolResult(assistantId, toolUseId, result, isError);
      },
      onDone: () => useChatStore.getState().completeMessage(assistantId),
      onError: (code, message) =>
        useChatStore.getState().setMessageError(assistantId, code, message),
    };

    sendChatMessage(apiMessages, callbacks, controller.signal);
  }, []);

  const handleStop = useCallback(() => {
    abortController?.abort();
    useChatStore.getState().setAbortController(null);
  }, [abortController]);

  // Escape closes the panel (not on full-screen mobile)
  useKeyboardShortcut(["Escape"], closePanel, !fullScreen);

  // Abort streaming on unmount to avoid wasted network/CPU
  useEffect(() => {
    return () => {
      const ctrl = useChatStore.getState().abortController;
      ctrl?.abort();
    };
  }, []);

  const hasMessages = messages.length > 0;

  return (
    <div className="flex h-full flex-col">
      {!fullScreen && (
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-medium text-foreground">Ask</h2>
          <button
            type="button"
            onClick={closePanel}
            className="rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
            aria-label="Close chat"
          >
            <X className="size-4" />
          </button>
        </div>
      )}

      {hasMessages ? (
        <ChatMessageList messages={messages} />
      ) : (
        <SuggestedQuestions onSelect={sendQuestion} />
      )}

      <ChatInput
        onSubmit={sendQuestion}
        isStreaming={isStreaming}
        onStop={handleStop}
      />
    </div>
  );
}
