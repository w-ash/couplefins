import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen, userEvent } from "@/test/test-utils";
import { FinalizationBanner } from "./FinalizationBanner";

const noop = () => {};

describe("FinalizationBanner", () => {
  it("renders open state with lock month button", () => {
    renderWithProviders(
      <FinalizationBanner
        isFinalized={false}
        finalizedAt={null}
        onFinalize={noop}
        onUnfinalize={noop}
        isPending={false}
      />,
    );
    expect(
      screen.getByText("This month is still open for changes"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /lock month/i }),
    ).toBeInTheDocument();
  });

  it("renders locked state with date and unlock button", () => {
    renderWithProviders(
      <FinalizationBanner
        isFinalized={true}
        finalizedAt="2026-03-10T18:30:00Z"
        onFinalize={noop}
        onUnfinalize={noop}
        isPending={false}
      />,
    );
    expect(screen.getByText("Month locked")).toBeInTheDocument();
    expect(screen.getByText(/Mar 10, 2026/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /unlock month/i }),
    ).toBeInTheDocument();
  });

  it("calls onFinalize when lock month button clicked", async () => {
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
    await user.click(screen.getByRole("button", { name: /lock month/i }));
    expect(onFinalize).toHaveBeenCalledOnce();
  });

  it("calls onUnfinalize when unlock month button clicked", async () => {
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
    await user.click(screen.getByRole("button", { name: /unlock month/i }));
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
    expect(screen.getByRole("button", { name: /lock month/i })).toBeDisabled();
  });
});
