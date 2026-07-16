import { fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatMessage as ChatMessageType } from "@/lib/chat";
import { renderWithProviders, screen } from "@/test/test-utils";
import { ChatMessage } from "./ChatMessage";

function makeMessage(overrides: Partial<ChatMessageType>): ChatMessageType {
  return {
    id: "msg-1",
    role: "assistant",
    content: "",
    ...overrides,
  };
}

describe("ChatMessage", () => {
  describe("user message", () => {
    it("renders text content", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({ role: "user", content: "Hello there" })}
        />,
      );
      expect(screen.getByText("Hello there")).toBeInTheDocument();
    });

    it("renders as plain text (no markdown parsing)", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({ role: "user", content: "**bold text**" })}
        />,
      );
      // User messages use whitespace-pre-wrap, not Streamdown
      expect(screen.getByText("**bold text**")).toBeInTheDocument();
    });
  });

  describe("assistant message", () => {
    it("renders text content", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({ content: "Here is your answer." })}
        />,
      );
      expect(screen.getByText("Here is your answer.")).toBeInTheDocument();
    });

    it("renders bold text via Streamdown", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({ content: "This is **important** info." })}
        />,
      );
      expect(screen.getByText("important")).toBeInTheDocument();
    });

    it("renders a markdown table", () => {
      const tableMarkdown = [
        "| Group | Spent |",
        "|---|---|",
        "| Food | $742.00 |",
        "| Travel | $200.00 |",
      ].join("\n");

      renderWithProviders(
        <ChatMessage message={makeMessage({ content: tableMarkdown })} />,
      );
      expect(screen.getByRole("table")).toBeInTheDocument();
      expect(screen.getByText("Food")).toBeInTheDocument();
      expect(screen.getByText("Travel")).toBeInTheDocument();
    });

    it("shows thinking indicator when streaming with no content", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({ content: "", isStreaming: true })}
        />,
      );
      expect(screen.getByLabelText("Thinking")).toBeInTheDocument();
    });

    it("hides thinking indicator once content arrives", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({
            content: "Starting response...",
            isStreaming: true,
          })}
        />,
      );
      expect(screen.queryByLabelText("Thinking")).not.toBeInTheDocument();
      expect(screen.getByText("Starting response...")).toBeInTheDocument();
    });

    it("strips echoed <user_data> tags from assistant prose", () => {
      // The model sees the tags in tool results and can echo them verbatim.
      renderWithProviders(
        <ChatMessage
          message={makeMessage({
            content: "You spent $50 at <user_data>Whole Foods</user_data>.",
          })}
        />,
      );
      expect(
        screen.getByText("You spent $50 at Whole Foods."),
      ).toBeInTheDocument();
    });

    it("leaves user message content untouched", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({
            role: "user",
            content: "what is <user_data> about?",
          })}
        />,
      );
      expect(
        screen.getByText("what is <user_data> about?"),
      ).toBeInTheDocument();
    });

    it("renders error state", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({
            error: { code: "TOOL_ERROR", message: "Tool failed" },
          })}
        />,
      );
      expect(screen.getByText("Tool failed")).toBeInTheDocument();
    });
  });

  describe("copy button", () => {
    let writeText: ReturnType<typeof vi.fn>;

    beforeEach(() => {
      writeText = vi.fn(() => Promise.resolve());
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText },
        configurable: true,
        writable: true,
      });
      vi.useFakeTimers({ shouldAdvanceTime: true });
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("is not rendered for user messages", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({ role: "user", content: "Hello" })}
        />,
      );
      expect(
        screen.queryByRole("button", { name: /copy message/i }),
      ).not.toBeInTheDocument();
    });

    it("is not rendered while streaming", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({ content: "partial", isStreaming: true })}
        />,
      );
      expect(
        screen.queryByRole("button", { name: /copy message/i }),
      ).not.toBeInTheDocument();
    });

    it("is not rendered on error bubbles", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({
            content: "",
            error: { code: "E", message: "broke" },
          })}
        />,
      );
      expect(
        screen.queryByRole("button", { name: /copy message/i }),
      ).not.toBeInTheDocument();
    });

    it("copies content to clipboard and flashes Copied", async () => {
      renderWithProviders(
        <ChatMessage message={makeMessage({ content: "**hello** world" })} />,
      );

      const button = screen.getByRole("button", { name: /copy message/i });
      fireEvent.click(button);
      await vi.waitFor(() =>
        expect(writeText).toHaveBeenCalledWith("**hello** world"),
      );

      await vi.waitFor(() =>
        expect(
          screen.getByRole("button", { name: /copied/i }),
        ).toBeInTheDocument(),
      );

      vi.advanceTimersByTime(1600);
      await vi.waitFor(() =>
        expect(
          screen.getByRole("button", { name: /copy message/i }),
        ).toBeInTheDocument(),
      );
    });
  });

  describe("tool calls", () => {
    it("renders tool call indicators", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({
            content: "Let me check that.",
            toolCalls: [{ id: "tc-1", name: "get_settlement_balance" }],
          })}
        />,
      );
      expect(screen.getByText(/settlement/)).toBeInTheDocument();
    });

    it("renders tool result cards when result is present", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({
            content: "Here is the settlement.",
            toolCalls: [
              {
                id: "tc-1",
                name: "get_settlement_balance",
                result: {
                  month: "2026-03",
                  is_finalized: false,
                  remaining_balance: 147.5,
                  from: "Alice",
                  to: "Bob",
                  gross_amount: 147.5,
                  net_from: "Alice",
                  net_to: "Bob",
                  uploads: [],
                },
              },
            ],
          })}
        />,
      );
      expect(screen.getByText(/Alice owes Bob/)).toBeInTheDocument();
      expect(screen.getByText("$147.50")).toBeInTheDocument();
    });

    it("does not render result card for error results", () => {
      renderWithProviders(
        <ChatMessage
          message={makeMessage({
            content: "Something went wrong.",
            toolCalls: [
              {
                id: "tc-1",
                name: "get_settlement_balance",
                result: { error: "failed" },
                isError: true,
              },
            ],
          })}
        />,
      );
      // Should show the indicator badge but not the result card
      expect(screen.getByText(/settlement/)).toBeInTheDocument();
      expect(screen.queryByText(/owes/)).not.toBeInTheDocument();
    });
  });
});
