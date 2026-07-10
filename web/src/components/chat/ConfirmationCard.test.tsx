import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConfirmationCard } from "./ConfirmationCard";

const BASE_PROPS = {
  actionId: "abc-123",
  description: "Set Food & Dining to $700.00 for April 2026 (household)",
  details: {
    group_name: "Food & Dining",
    amount: 700,
    year: 2026,
    month: 4,
    scope: "household",
  },
  toolName: "update_budget",
  onConfirm: vi.fn(),
  onCancel: vi.fn(),
};

describe("ConfirmationCard", () => {
  it("renders description and buttons in pending state", () => {
    render(<ConfirmationCard {...BASE_PROPS} state="pending" />);
    expect(screen.getByText(BASE_PROPS.description)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
  });

  it("calls onConfirm with actionId when Confirm clicked", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmationCard
        {...BASE_PROPS}
        state="pending"
        onConfirm={onConfirm}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).toHaveBeenCalledWith("abc-123");
  });

  it("calls onCancel with actionId when Cancel clicked", async () => {
    const onCancel = vi.fn();
    render(
      <ConfirmationCard {...BASE_PROPS} state="pending" onCancel={onCancel} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledWith("abc-123");
  });

  it("disables buttons in loading state", () => {
    render(<ConfirmationCard {...BASE_PROPS} state="loading" />);
    expect(screen.getByRole("button", { name: /confirm/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("shows Updated label in confirmed state", () => {
    render(<ConfirmationCard {...BASE_PROPS} state="confirmed" />);
    expect(screen.getByText("Updated")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm" }),
    ).not.toBeInTheDocument();
  });

  it("shows Cancelled label in cancelled state", () => {
    render(<ConfirmationCard {...BASE_PROPS} state="cancelled" />);
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirm" }),
    ).not.toBeInTheDocument();
  });
});

describe("generic DetailDisplay (v1.8.2 mutations)", () => {
  it("renders unknown mutation details through the generic card", () => {
    render(
      <ConfirmationCard
        {...BASE_PROPS}
        toolName="finalize_period"
        description="Finalize March 2026 (lock the month)"
        details={{
          year: 2026,
          month: 3,
          warnings: ["No upload from Bob"],
          transaction_count: 82,
        }}
        state="pending"
      />,
    );
    expect(screen.getByText("transaction count")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText("No upload from Bob")).toBeInTheDocument();
  });

  it("renders batch split proposals as a table via the generic card", () => {
    render(
      <ConfirmationCard
        {...BASE_PROPS}
        toolName="update_transaction_split"
        description="Change splits on 2 transactions to 60/40"
        details={{
          count: 2,
          splits: [
            {
              merchant: "<user_data>Rent Co</user_data>",
              date: "2026-03-01",
              current_split: "50/50",
              new_split: "60/40",
            },
            {
              merchant: "<user_data>Rent Co</user_data>",
              date: "2026-04-01",
              current_split: "50/50",
              new_split: "60/40",
            },
          ],
        }}
        state="pending"
      />,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getAllByText("Rent Co")).toHaveLength(2);
    expect(screen.getAllByText("60/40")).toHaveLength(2);
  });
});
