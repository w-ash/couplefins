import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, userEvent } from "@/test/test-utils";
import { FinalizationBanner } from "./FinalizationBanner";

const noop = () => {};

describe("FinalizationBanner", () => {
  it("renders open state with finalize button", () => {
    renderWithProviders(
      <FinalizationBanner
        isFinalized={false}
        finalizedAt={null}
        onFinalize={noop}
        onUnfinalize={noop}
        isPending={false}
      />,
    );
    expect(screen.getByText("Month not yet finalized")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /finalize/i }),
    ).toBeInTheDocument();
  });

  it("renders finalized state with date and unlock button", () => {
    renderWithProviders(
      <FinalizationBanner
        isFinalized={true}
        finalizedAt="2026-03-10T18:30:00Z"
        onFinalize={noop}
        onUnfinalize={noop}
        isPending={false}
      />,
    );
    expect(screen.getByText("Finalized")).toBeInTheDocument();
    expect(screen.getByText(/Mar 10, 2026/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /unlock/i })).toBeInTheDocument();
  });

  it("calls onFinalize when finalize button clicked", async () => {
    const onFinalize = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <FinalizationBanner
        isFinalized={false}
        finalizedAt={null}
        onFinalize={onFinalize}
        onUnfinalize={noop}
        isPending={false}
      />,
    );
    await user.click(screen.getByRole("button", { name: /finalize/i }));
    expect(onFinalize).toHaveBeenCalledOnce();
  });

  it("calls onUnfinalize when unlock button clicked", async () => {
    const onUnfinalize = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <FinalizationBanner
        isFinalized={true}
        finalizedAt="2026-03-10T18:30:00Z"
        onFinalize={noop}
        onUnfinalize={onUnfinalize}
        isPending={false}
      />,
    );
    await user.click(screen.getByRole("button", { name: /unlock/i }));
    expect(onUnfinalize).toHaveBeenCalledOnce();
  });

  it("disables buttons when pending", () => {
    renderWithProviders(
      <FinalizationBanner
        isFinalized={false}
        finalizedAt={null}
        onFinalize={noop}
        onUnfinalize={noop}
        isPending={true}
      />,
    );
    expect(screen.getByRole("button", { name: /finalize/i })).toBeDisabled();
  });
});
