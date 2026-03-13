import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Upload } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { PageEmpty, PageError, PageLoading } from "./PageStates";

describe("PageLoading", () => {
  it("renders spinner and label", () => {
    render(<PageLoading label="Loading dashboard..." />);
    expect(screen.getByText("Loading dashboard...")).toBeInTheDocument();
    const svg = document.querySelector("svg.animate-spin");
    expect(svg).toBeInTheDocument();
  });
});

describe("PageError", () => {
  it("renders error message and Try Again button", () => {
    const onRetry = vi.fn();
    render(
      <PageError error={new Error("Something broke")} onRetry={onRetry} />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Something broke")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Try Again" }),
    ).toBeInTheDocument();
  });

  it("calls onRetry when Try Again is clicked", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<PageError error={new Error("fail")} onRetry={onRetry} />);
    await user.click(screen.getByRole("button", { name: "Try Again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe("PageEmpty", () => {
  it("renders icon, heading, description, and action", () => {
    render(
      <PageEmpty
        icon={<Upload data-testid="icon" />}
        heading="No data"
        description="Nothing to show."
        action={<button type="button">Do something</button>}
      />,
    );
    expect(screen.getByTestId("icon")).toBeInTheDocument();
    expect(screen.getByText("No data")).toBeInTheDocument();
    expect(screen.getByText("Nothing to show.")).toBeInTheDocument();
    expect(screen.getByText("Do something")).toBeInTheDocument();
  });

  it("renders without action slot", () => {
    render(
      <PageEmpty icon={<Upload />} heading="Empty" description="No items." />,
    );
    expect(screen.getByText("Empty")).toBeInTheDocument();
    expect(screen.getByText("No items.")).toBeInTheDocument();
  });
});
