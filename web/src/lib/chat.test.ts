import { beforeEach, describe, expect, it } from "vitest";
import { useChatStore } from "./chat";

describe("chat store", () => {
  beforeEach(() => {
    useChatStore.setState({
      messages: [],
      isStreaming: false,
      abortController: null,
      isPanelOpen: false,
      confirmationStates: {},
    });
  });

  it("starts with empty messages and not streaming", () => {
    const state = useChatStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.isStreaming).toBe(false);
    expect(state.isPanelOpen).toBe(false);
  });

  it("adds a user message", () => {
    const id = useChatStore.getState().addUserMessage("Hello");
    const msg = useChatStore.getState().messages[0];
    expect(msg.id).toBe(id);
    expect(msg.role).toBe("user");
    expect(msg.content).toBe("Hello");
  });

  it("starts an assistant message in streaming state", () => {
    const id = useChatStore.getState().startAssistantMessage();
    const state = useChatStore.getState();
    expect(state.isStreaming).toBe(true);
    const msg = state.messages[0];
    expect(msg.id).toBe(id);
    expect(msg.role).toBe("assistant");
    expect(msg.content).toBe("");
    expect(msg.isStreaming).toBe(true);
  });

  it("appends tokens to a message", () => {
    const id = useChatStore.getState().startAssistantMessage();
    useChatStore.getState().appendToken(id, "Hello");
    useChatStore.getState().appendToken(id, " world");
    expect(useChatStore.getState().messages[0].content).toBe("Hello world");
  });

  it("completes a message and clears streaming state", () => {
    const id = useChatStore.getState().startAssistantMessage();
    useChatStore.getState().appendToken(id, "Done");
    useChatStore.getState().completeMessage(id);

    const state = useChatStore.getState();
    expect(state.isStreaming).toBe(false);
    expect(state.abortController).toBeNull();
    expect(state.messages[0].isStreaming).toBe(false);
  });

  it("sets error on a message", () => {
    const id = useChatStore.getState().startAssistantMessage();
    useChatStore
      .getState()
      .setMessageError(id, "TEST_ERROR", "Something broke");

    const state = useChatStore.getState();
    expect(state.isStreaming).toBe(false);
    expect(state.messages[0].error).toEqual({
      code: "TEST_ERROR",
      message: "Something broke",
    });
  });

  it("adds and resolves tool calls", () => {
    const msgId = useChatStore.getState().startAssistantMessage();
    useChatStore
      .getState()
      .addToolCall(msgId, "tc-1", "get_settlement_balance");

    let msg = useChatStore.getState().messages[0];
    expect(msg.toolCalls).toHaveLength(1);
    expect(msg.toolCalls?.[0].name).toBe("get_settlement_balance");
    expect(msg.toolCalls?.[0].result).toBeUndefined();

    useChatStore
      .getState()
      .setToolResult(msgId, "tc-1", { amount: 147.5 }, false);

    msg = useChatStore.getState().messages[0];
    expect(msg.toolCalls?.[0].result).toEqual({ amount: 147.5 });
    expect(msg.toolCalls?.[0].isError).toBe(false);
  });

  it("adds and resolves code executions", () => {
    const msgId = useChatStore.getState().startAssistantMessage();
    useChatStore
      .getState()
      .addCodeExecution(msgId, "srvtoolu_1", "print(total)");

    let msg = useChatStore.getState().messages[0];
    expect(msg.codeExecutions).toHaveLength(1);
    expect(msg.codeExecutions?.[0].command).toBe("print(total)");
    expect(msg.codeExecutions?.[0].returnCode).toBeUndefined();

    useChatStore
      .getState()
      .setCodeResult(msgId, "srvtoolu_1", "412.50\n", "", 0);

    msg = useChatStore.getState().messages[0];
    expect(msg.codeExecutions?.[0]).toEqual({
      id: "srvtoolu_1",
      command: "print(total)",
      stdout: "412.50\n",
      stderr: "",
      returnCode: 0,
    });
  });

  it("toggles panel state", () => {
    expect(useChatStore.getState().isPanelOpen).toBe(false);
    useChatStore.getState().togglePanel();
    expect(useChatStore.getState().isPanelOpen).toBe(true);
    useChatStore.getState().togglePanel();
    expect(useChatStore.getState().isPanelOpen).toBe(false);
  });

  it("clears all messages and confirmation states", () => {
    useChatStore.getState().addUserMessage("Hi");
    useChatStore.getState().startAssistantMessage();
    useChatStore.getState().setConfirmationState("action-1", "pending");
    expect(useChatStore.getState().messages).toHaveLength(2);

    useChatStore.getState().clearMessages();
    const state = useChatStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.isStreaming).toBe(false);
    expect(state.confirmationStates).toEqual({});
  });

  describe("removeLastAssistantMessage", () => {
    it("removes a trailing assistant message", () => {
      useChatStore.getState().addUserMessage("Hi");
      useChatStore.getState().startAssistantMessage();
      expect(useChatStore.getState().messages).toHaveLength(2);

      useChatStore.getState().removeLastAssistantMessage();
      const state = useChatStore.getState();
      expect(state.messages).toHaveLength(1);
      expect(state.messages[0].role).toBe("user");
    });

    it("is a no-op when the trailing message is a user message", () => {
      useChatStore.getState().addUserMessage("Hi");
      useChatStore.getState().removeLastAssistantMessage();
      expect(useChatStore.getState().messages).toHaveLength(1);
    });

    it("is a no-op on empty state", () => {
      useChatStore.getState().removeLastAssistantMessage();
      expect(useChatStore.getState().messages).toEqual([]);
    });
  });

  it("stores and clears abort controller", () => {
    const controller = new AbortController();
    useChatStore.getState().setAbortController(controller);
    expect(useChatStore.getState().abortController).toBe(controller);

    useChatStore.getState().setAbortController(null);
    expect(useChatStore.getState().abortController).toBeNull();
  });
});
