import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ToolCallIndicator } from "./ToolCallIndicator";

describe("ToolCallIndicator", () => {
  it("shows Proposing for in-flight writes", () => {
    render(
      <ToolCallIndicator
        toolCall={{ id: "1", name: "finalize_period", kind: "write" }}
      />,
    );
    expect(screen.getByText("Proposing month lock…")).toBeInTheDocument();
  });

  it("shows Looking up for in-flight reads", () => {
    render(
      <ToolCallIndicator
        toolCall={{ id: "1", name: "get_upload_history", kind: "read" }}
      />,
    );
    expect(screen.getByText("Looking up upload history…")).toBeInTheDocument();
  });

  it("shows Looking up (never Proposing) for agentic tools", () => {
    render(
      <ToolCallIndicator
        toolCall={{ id: "1", name: "delegate_analysis", kind: "agentic" }}
      />,
    );
    expect(screen.getByText("Looking up deep analysis…")).toBeInTheDocument();
  });

  it("shows Checked when the result arrived", () => {
    render(
      <ToolCallIndicator
        toolCall={{
          id: "1",
          name: "record_settlement",
          kind: "write",
          result: {},
        }}
      />,
    );
    expect(screen.getByText("Checked settlement")).toBeInTheDocument();
  });
});
