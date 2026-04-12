import { fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatMessage } from "@/lib/chat";
import { useChatStore } from "@/lib/chat";
import { renderWithProviders, screen } from "@/test/test-utils";

vi.mock("@/api/chat-sse", () => ({
  sendChatMessage: vi.fn(() => Promise.resolve()),
}));

import { sendChatMessage } from "@/api/chat-sse";
import { ChatPanel } from "./ChatPanel";

function seedMessages(items: Partial<ChatMessage>[]) {
  const messages: ChatMessage[] = items.map((item, i) => ({
    id: `m-${i}`,
    role: "user",
    content: `msg ${i}`,
    ...item,
  }));
  useChatStore.setState({ messages });
}

describe("ChatPanel", () => {
  beforeEach(() => {
    vi.mocked(sendChatMessage).mockClear();
    useChatStore.setState({
      messages: [],
      isStreaming: false,
      abortController: null,
      isPanelOpen: false,
      confirmationStates: {},
    });
  });

  it("hides the controls row when there are no messages and no limit error", () => {
    renderWithProviders(<ChatPanel />);
    expect(
      screen.queryByRole("button", { name: /new conversation/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /regenerate/i }),
    ).not.toBeInTheDocument();
  });

  it("shows New conversation once messages exist and clears them on click", () => {
    seedMessages([
      { role: "user", content: "Hi" },
      { role: "assistant", content: "Hello" },
    ]);

    renderWithProviders(<ChatPanel />);

    const newButton = screen.getByRole("button", { name: /new conversation/i });
    fireEvent.click(newButton);

    expect(useChatStore.getState().messages).toEqual([]);
  });

  it("hides Regenerate when the last message is a user message", () => {
    seedMessages([{ role: "user", content: "Hi" }]);
    renderWithProviders(<ChatPanel />);
    expect(
      screen.queryByRole("button", { name: /regenerate/i }),
    ).not.toBeInTheDocument();
  });

  it("hides Regenerate while streaming", () => {
    seedMessages([
      { role: "user", content: "Hi" },
      { role: "assistant", content: "partial", isStreaming: true },
    ]);
    useChatStore.setState({ isStreaming: true });
    renderWithProviders(<ChatPanel />);
    expect(
      screen.queryByRole("button", { name: /regenerate/i }),
    ).not.toBeInTheDocument();
  });

  it("regenerates by removing the last assistant message and streaming a new one", () => {
    seedMessages([
      { role: "user", content: "Hi" },
      { role: "assistant", content: "wrong", id: "assistant-1" },
    ]);

    renderWithProviders(<ChatPanel />);

    const regenerate = screen.getByRole("button", { name: /regenerate/i });
    fireEvent.click(regenerate);

    const state = useChatStore.getState();
    expect(state.messages).toHaveLength(2);
    expect(state.messages[0].role).toBe("user");
    expect(state.messages[1].role).toBe("assistant");
    expect(state.messages[1].id).not.toBe("assistant-1");
    expect(state.messages[1].isStreaming).toBe(true);
    expect(sendChatMessage).toHaveBeenCalledTimes(1);
  });

  it("surfaces the limit error and blocks sending when the conversation is full", () => {
    const full: Partial<ChatMessage>[] = Array.from({ length: 50 }, (_, i) => ({
      role: i % 2 === 0 ? "user" : "assistant",
      content: `msg ${i}`,
    }));
    seedMessages(full);

    renderWithProviders(<ChatPanel />);

    const textarea = screen.getByPlaceholderText(/ask about your finances/i);
    fireEvent.change(textarea, { target: { value: "one more question" } });
    fireEvent.keyDown(textarea, { key: "Enter" });

    expect(screen.getByRole("alert")).toHaveTextContent(
      /conversation is full/i,
    );
    const newButton = screen.getByRole("button", { name: /new conversation/i });
    expect(newButton.className).toMatch(/bg-primary/);
    expect(sendChatMessage).not.toHaveBeenCalled();

    fireEvent.click(newButton);
    expect(useChatStore.getState().messages).toEqual([]);
    expect(
      screen.queryByRole("alert", { name: /conversation is full/i }),
    ).not.toBeInTheDocument();
  });
});
