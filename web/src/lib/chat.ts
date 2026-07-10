import { create } from "zustand";

export interface ToolCall {
  id: string;
  name: string;
  result?: unknown;
  isError?: boolean;
}

export interface CodeExecution {
  id: string;
  command: string;
  stdout?: string;
  stderr?: string;
  returnCode?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  error?: { code: string; message: string };
  toolCalls?: ToolCall[];
  codeExecutions?: CodeExecution[];
}

export type ConfirmationState =
  | "pending"
  | "loading"
  | "confirmed"
  | "cancelled";

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  abortController: AbortController | null;
  isPanelOpen: boolean;
  confirmationStates: Record<string, ConfirmationState>;

  addUserMessage: (text: string) => string;
  startAssistantMessage: () => string;
  appendToken: (id: string, text: string) => void;
  addToolCall: (messageId: string, toolId: string, name: string) => void;
  setToolResult: (
    messageId: string,
    toolId: string,
    result: unknown,
    isError: boolean,
  ) => void;
  addCodeExecution: (
    messageId: string,
    codeId: string,
    command: string,
  ) => void;
  setCodeResult: (
    messageId: string,
    codeId: string,
    stdout: string,
    stderr: string,
    returnCode: number,
  ) => void;
  completeMessage: (id: string) => void;
  setMessageError: (id: string, code: string, message: string) => void;
  removeLastAssistantMessage: () => void;
  setAbortController: (c: AbortController | null) => void;
  setPanelOpen: (open: boolean) => void;
  togglePanel: () => void;
  clearMessages: () => void;
  setConfirmationState: (actionId: string, state: ConfirmationState) => void;
}

function updateMessage(
  messages: ChatMessage[],
  id: string,
  updater: (msg: ChatMessage) => ChatMessage,
): ChatMessage[] {
  return messages.map((m) => (m.id === id ? updater(m) : m));
}

export const useChatStore = create<ChatState>()((set) => ({
  messages: [],
  isStreaming: false,
  abortController: null,
  isPanelOpen: false,
  confirmationStates: {},

  addUserMessage: (text) => {
    const id = crypto.randomUUID();
    set((s) => ({
      messages: [...s.messages, { id, role: "user" as const, content: text }],
    }));
    return id;
  },

  startAssistantMessage: () => {
    const id = crypto.randomUUID();
    set((s) => ({
      messages: [
        ...s.messages,
        { id, role: "assistant" as const, content: "", isStreaming: true },
      ],
      isStreaming: true,
    }));
    return id;
  },

  appendToken: (id, text) =>
    set((s) => ({
      messages: updateMessage(s.messages, id, (m) => ({
        ...m,
        content: m.content + text,
      })),
    })),

  addToolCall: (messageId, toolId, name) =>
    set((s) => ({
      messages: updateMessage(s.messages, messageId, (m) => ({
        ...m,
        toolCalls: [...(m.toolCalls ?? []), { id: toolId, name }],
      })),
    })),

  setToolResult: (messageId, toolId, result, isError) =>
    set((s) => ({
      messages: updateMessage(s.messages, messageId, (m) => ({
        ...m,
        toolCalls: (m.toolCalls ?? []).map((tc) =>
          tc.id === toolId ? { ...tc, result, isError } : tc,
        ),
      })),
    })),

  addCodeExecution: (messageId, codeId, command) =>
    set((s) => ({
      messages: updateMessage(s.messages, messageId, (m) => ({
        ...m,
        codeExecutions: [...(m.codeExecutions ?? []), { id: codeId, command }],
      })),
    })),

  setCodeResult: (messageId, codeId, stdout, stderr, returnCode) =>
    set((s) => ({
      messages: updateMessage(s.messages, messageId, (m) => ({
        ...m,
        codeExecutions: (m.codeExecutions ?? []).map((ce) =>
          ce.id === codeId ? { ...ce, stdout, stderr, returnCode } : ce,
        ),
      })),
    })),

  completeMessage: (id) =>
    set((s) => ({
      messages: updateMessage(s.messages, id, (m) => ({
        ...m,
        isStreaming: false,
      })),
      isStreaming: false,
      abortController: null,
    })),

  setMessageError: (id, code, message) =>
    set((s) => ({
      messages: updateMessage(s.messages, id, (m) => ({
        ...m,
        isStreaming: false,
        error: { code, message },
      })),
      isStreaming: false,
      abortController: null,
    })),

  removeLastAssistantMessage: () =>
    set((s) => {
      const last = s.messages.at(-1);
      if (!last || last.role !== "assistant") return s;
      return { messages: s.messages.slice(0, -1) };
    }),

  setAbortController: (c) => set({ abortController: c }),

  setPanelOpen: (open) => set({ isPanelOpen: open }),

  togglePanel: () => set((s) => ({ isPanelOpen: !s.isPanelOpen })),

  clearMessages: () =>
    set({
      messages: [],
      isStreaming: false,
      abortController: null,
      confirmationStates: {},
    }),

  setConfirmationState: (actionId, state) =>
    set((s) => ({
      confirmationStates: { ...s.confirmationStates, [actionId]: state },
    })),
}));
