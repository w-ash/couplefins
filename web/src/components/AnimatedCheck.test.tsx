import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnimatedCheck } from "./AnimatedCheck";

describe("AnimatedCheck", () => {
  it("renders SVG with circle and path", () => {
    const { container } = render(<AnimatedCheck />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg?.querySelector("circle")).toBeInTheDocument();
    expect(svg?.querySelector("path")).toBeInTheDocument();
  });

  it("applies custom size", () => {
    const { container } = render(<AnimatedCheck size={32} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "32");
    expect(svg).toHaveAttribute("height", "32");
  });

  it("has animated-check class for reduced-motion targeting", () => {
    const { container } = render(<AnimatedCheck />);
    const svg = container.querySelector("svg");
    expect(svg?.classList.contains("animated-check")).toBe(true);
  });

  it("is hidden from assistive technology", () => {
    const { container } = render(<AnimatedCheck />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });
});
