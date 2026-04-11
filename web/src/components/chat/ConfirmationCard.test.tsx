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
