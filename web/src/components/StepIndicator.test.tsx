import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StepIndicator } from "./StepIndicator";

describe("StepIndicator", () => {
  it("renders all three step labels", () => {
    render(<StepIndicator currentStepIndex={0} />);
    expect(screen.getByText("Select file")).toBeInTheDocument();
    expect(screen.getByText("Preview")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("marks the current step with aria-current", () => {
    const { container } = render(<StepIndicator currentStepIndex={1} />);
    const current = container.querySelector('[aria-current="step"]');
    expect(current).toBeInTheDocument();
    // Only one step should be marked current
    expect(container.querySelectorAll('[aria-current="step"]')).toHaveLength(1);
  });

  it("has an accessible nav landmark", () => {
    render(<StepIndicator currentStepIndex={0} />);
    expect(
      screen.getByRole("navigation", { name: "Upload progress" }),
    ).toBeInTheDocument();
  });

  it("shows completed check for past steps", () => {
    const { container } = render(<StepIndicator currentStepIndex={2} />);
    // At index 2, steps 0 and 1 are completed — they should contain SVG check icons
    const checkIcons = container.querySelectorAll("svg");
    expect(checkIcons.length).toBeGreaterThanOrEqual(2);
  });

  it("highlights correct step for each index", () => {
    const { rerender, container } = render(
      <StepIndicator currentStepIndex={0} />,
    );
    expect(
      container.querySelector('[aria-current="step"]'),
    ).toBeInTheDocument();

    rerender(<StepIndicator currentStepIndex={1} />);
    expect(
      container.querySelector('[aria-current="step"]'),
    ).toBeInTheDocument();

    rerender(<StepIndicator currentStepIndex={2} />);
    expect(
      container.querySelector('[aria-current="step"]'),
    ).toBeInTheDocument();
  });
});
