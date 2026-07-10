import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { isMutationTool, ToolCallIndicator } from "./ToolCallIndicator";

describe("isMutationTool", () => {
  // Backend registry names (pinned by test_read_write_naming_convention in
  // the backend suite): reads are get_*/search_*, writes are anything else.
  it("classifies read tool names as lookups", () => {
    for (const name of [
      "get_settlement_balance",
      "get_upload_history",
      "search_transactions",
    ]) {
      expect(isMutationTool(name)).toBe(false);
    }
  });

  it("classifies write tool names as mutations", () => {
    for (const name of [
      "update_budget",
      "delete_budget",
      "copy_budgets",
      "manage_category_group",
      "map_categories",
      "set_category_personal",
      "finalize_period",
      "unfinalize_period",
      "record_settlement",
      "waive_settlement",
      "delete_settlement",
      "link_settlement_transaction",
      "unlink_settlement_transaction",
      "manage_settlement_merchant",
      "update_transaction_split",
      "bulk_update_transactions",
    ]) {
      expect(isMutationTool(name)).toBe(true);
    }
  });

  it("classifies agentic read overrides as lookups despite their names", () => {
    expect(isMutationTool("delegate_analysis")).toBe(false);
  });
});

describe("ToolCallIndicator", () => {
  it("shows Proposing for in-flight mutations", () => {
    render(
      <ToolCallIndicator toolCall={{ id: "1", name: "finalize_period" }} />,
    );
    expect(screen.getByText("Proposing month lock…")).toBeInTheDocument();
  });

  it("shows Looking up for in-flight reads", () => {
    render(
      <ToolCallIndicator toolCall={{ id: "1", name: "get_upload_history" }} />,
    );
    expect(screen.getByText("Looking up upload history…")).toBeInTheDocument();
  });

  it("shows Looking up (never Proposing) for delegate_analysis", () => {
    render(
      <ToolCallIndicator toolCall={{ id: "1", name: "delegate_analysis" }} />,
    );
    expect(screen.getByText("Looking up deep analysis…")).toBeInTheDocument();
  });

  it("shows Checked when the result arrived", () => {
    render(
      <ToolCallIndicator
        toolCall={{ id: "1", name: "record_settlement", result: {} }}
      />,
    );
    expect(screen.getByText("Checked settlement")).toBeInTheDocument();
  });
});
