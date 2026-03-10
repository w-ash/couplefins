import { Upload } from "lucide-react";
import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/test/test-utils";
import { NavItem } from "./NavItem";

describe("NavItem", () => {
  it("renders as a link when enabled", () => {
    renderWithProviders(<NavItem to="/upload" label="Upload" icon={Upload} />);
    const link = screen.getByRole("link", { name: "Upload" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/upload");
  });

  it("renders as a span when disabled", () => {
    renderWithProviders(
      <NavItem to="/dashboard" label="Dashboard" icon={Upload} disabled />,
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("has cursor-not-allowed class when disabled", () => {
    renderWithProviders(
      <NavItem to="/dashboard" label="Dashboard" icon={Upload} disabled />,
    );
    expect(screen.getByText("Dashboard").closest("span")).toHaveClass(
      "cursor-not-allowed",
    );
  });

  it("applies active styles when route matches", () => {
    renderWithProviders(<NavItem to="/upload" label="Upload" icon={Upload} />, {
      routerProps: { initialEntries: ["/upload"] },
    });
    const link = screen.getByRole("link", { name: "Upload" });
    expect(link).toHaveClass("border-primary");
    expect(link).toHaveClass("font-medium");
  });

  it("applies inactive styles when route does not match", () => {
    renderWithProviders(<NavItem to="/upload" label="Upload" icon={Upload} />, {
      routerProps: { initialEntries: ["/settings"] },
    });
    const link = screen.getByRole("link", { name: "Upload" });
    expect(link).toHaveClass("text-muted-foreground");
    expect(link).not.toHaveClass("border-primary");
  });

  it("has aria-disabled and title on disabled items", () => {
    renderWithProviders(
      <NavItem to="/dashboard" label="Dashboard" icon={Upload} disabled />,
    );
    const span = screen.getByText("Dashboard").closest("span");
    expect(span).toHaveAttribute("aria-disabled", "true");
    expect(span).toHaveAttribute("title", "Coming soon");
  });
});
