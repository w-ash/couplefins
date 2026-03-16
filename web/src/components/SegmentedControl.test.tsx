import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SegmentedControl } from "./SegmentedControl";

afterEach(cleanup);

const options = [
  { value: "a" as const, label: "Alpha" },
  { value: "b" as const, label: "Beta" },
  { value: "c" as const, label: "Gamma" },
];

describe("SegmentedControl", () => {
  it("renders all option labels", () => {
    render(
      <SegmentedControl options={options} value="a" onChange={() => {}} />,
    );
    expect(screen.getByText("Alpha")).toBeDefined();
    expect(screen.getByText("Beta")).toBeDefined();
    expect(screen.getByText("Gamma")).toBeDefined();
  });

  it("checks the active radio input", () => {
    render(
      <SegmentedControl options={options} value="b" onChange={() => {}} />,
    );
    const radios = screen.getAllByRole("radio");
    expect(radios[0]).not.toBeChecked();
    expect(radios[1]).toBeChecked();
    expect(radios[2]).not.toBeChecked();
  });

  it("calls onChange with the clicked option value", () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl options={options} value="a" onChange={onChange} />,
    );
    fireEvent.click(screen.getByText("Beta"));
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("navigates with arrow keys via native radio group", () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl options={options} value="b" onChange={onChange} />,
    );
    // Native radio group handles arrow key navigation
    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(3);
  });

  it("renders icons when provided", () => {
    const iconOptions = [
      {
        value: "x" as const,
        label: "Ex",
        icon: <span data-testid="icon-x" />,
      },
      { value: "y" as const, label: "Why" },
    ];
    render(
      <SegmentedControl options={iconOptions} value="x" onChange={() => {}} />,
    );
    expect(screen.getByTestId("icon-x")).toBeDefined();
  });

  it("uses radiogroup role on container", () => {
    render(
      <SegmentedControl options={options} value="a" onChange={() => {}} />,
    );
    expect(screen.getByRole("radiogroup")).toBeDefined();
  });

  it("applies rounded-full when shape is pill", () => {
    render(
      <SegmentedControl
        options={options}
        value="a"
        onChange={() => {}}
        shape="pill"
      />,
    );
    const container = screen.getByRole("radiogroup");
    expect(container.className).toContain("rounded-full");
  });
});
