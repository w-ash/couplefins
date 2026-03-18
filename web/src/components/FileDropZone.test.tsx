import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FileDropZone } from "./FileDropZone";

function renderDropZone(
  overrides: Partial<{
    accept: string;
    onFile: (file: File) => void;
    disabled: boolean;
    currentFile: File | null;
    maxSizeBytes: number;
  }> = {},
) {
  const onFile = overrides.onFile ?? vi.fn();
  const result = render(
    <FileDropZone
      accept={overrides.accept ?? ".csv"}
      onFile={onFile}
      disabled={overrides.disabled ?? false}
      currentFile={overrides.currentFile ?? null}
      maxSizeBytes={overrides.maxSizeBytes}
    />,
  );
  return { onFile, ...result };
}

function getZone() {
  return screen
    .getByText(/Drop your CSV here|Change file/)
    .closest("label") as HTMLLabelElement;
}

function csvFile(name = "test.csv", content = "Date,Merchant\n") {
  return new File([content], name, { type: "text/csv" });
}

describe("FileDropZone", () => {
  it("renders idle state with drop prompt", () => {
    renderDropZone();
    expect(
      screen.getByText("Drop your CSV here, or click to browse"),
    ).toBeInTheDocument();
    expect(screen.getByText(".csv files only")).toBeInTheDocument();
  });

  it("applies drag-over styling on dragEnter and removes on dragLeave", () => {
    renderDropZone();
    const zone = getZone();

    fireEvent.dragEnter(zone, { dataTransfer: { files: [] } });
    expect(zone.className).toContain("border-primary");
    expect(zone.className).toContain("bg-accent");

    fireEvent.dragLeave(zone, { dataTransfer: { files: [] } });
    expect(zone.className).not.toContain("border-primary");
    expect(zone.className).toContain("border-border");
  });

  it("handles nested dragEnter/dragLeave correctly", () => {
    renderDropZone();
    const zone = getZone();

    fireEvent.dragEnter(zone, { dataTransfer: { files: [] } });
    fireEvent.dragEnter(zone, { dataTransfer: { files: [] } });
    expect(zone.className).toContain("border-primary");

    fireEvent.dragLeave(zone, { dataTransfer: { files: [] } });
    expect(zone.className).toContain("border-primary");

    fireEvent.dragLeave(zone, { dataTransfer: { files: [] } });
    expect(zone.className).not.toContain("border-primary");
  });

  it("calls onFile when a file is selected via input change", () => {
    const { onFile, container } = renderDropZone();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = csvFile();

    fireEvent.change(input, { target: { files: [file] } });
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("shows file name and size when currentFile is provided", () => {
    renderDropZone({
      currentFile: new File(["x".repeat(1024)], "march-2026.csv", {
        type: "text/csv",
      }),
    });
    expect(screen.getByText("march-2026.csv")).toBeInTheDocument();
    expect(screen.getByText("1.0 KB")).toBeInTheDocument();
    expect(screen.getByText("Change file")).toBeInTheDocument();
    expect(
      screen.queryByText("Drop your CSV here, or click to browse"),
    ).not.toBeInTheDocument();
  });

  it("calls onFile when a CSV file is dropped", () => {
    const { onFile } = renderDropZone();
    const zone = getZone();
    const file = csvFile();

    fireEvent.drop(zone, { dataTransfer: { files: [file] } });
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("clears drag-over state after drop", () => {
    renderDropZone();
    const zone = getZone();

    fireEvent.dragEnter(zone, { dataTransfer: { files: [] } });
    expect(zone.className).toContain("border-primary");

    fireEvent.drop(zone, { dataTransfer: { files: [csvFile()] } });
    expect(zone.className).not.toContain("border-primary");
  });

  it("rejects non-CSV files with an error", () => {
    const { onFile } = renderDropZone();
    const zone = getZone();
    const txtFile = new File(["hello"], "readme.txt", { type: "text/plain" });

    fireEvent.drop(zone, { dataTransfer: { files: [txtFile] } });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Only .csv files are accepted",
    );
  });

  it("clears error when a valid file is subsequently dropped", () => {
    const { onFile } = renderDropZone();
    const zone = getZone();
    const txtFile = new File(["hello"], "readme.txt", { type: "text/plain" });

    fireEvent.drop(zone, { dataTransfer: { files: [txtFile] } });
    expect(screen.getByRole("alert")).toBeInTheDocument();

    fireEvent.drop(zone, { dataTransfer: { files: [csvFile()] } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(onFile).toHaveBeenCalled();
  });

  it("prevents interaction when disabled", () => {
    const { onFile } = renderDropZone({ disabled: true });
    const zone = screen
      .getByText(".csv files only")
      .closest("label") as HTMLLabelElement;

    expect(zone.className).toContain("opacity-50");
    expect(zone.className).toContain("cursor-not-allowed");
    expect(zone).toHaveAttribute("tabindex", "-1");

    fireEvent.drop(zone, { dataTransfer: { files: [csvFile()] } });
    expect(onFile).not.toHaveBeenCalled();
  });

  it("opens file picker on Enter key", () => {
    const { container } = renderDropZone();
    const zone = screen
      .getByText("Drop your CSV here, or click to browse")
      .closest("label") as HTMLLabelElement;
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");

    fireEvent.keyDown(zone, { key: "Enter" });
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it("opens file picker on Space key", () => {
    const { container } = renderDropZone();
    const zone = screen
      .getByText("Drop your CSV here, or click to browse")
      .closest("label") as HTMLLabelElement;
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const clickSpy = vi.spyOn(input, "click");

    fireEvent.keyDown(zone, { key: " " });
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it("rejects empty files with an error on drop", () => {
    const { onFile } = renderDropZone();
    const zone = getZone();
    const emptyFile = new File([], "empty.csv", { type: "text/csv" });

    fireEvent.drop(zone, { dataTransfer: { files: [emptyFile] } });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("File is empty");
  });

  it("rejects empty files on input change", () => {
    const { onFile, container } = renderDropZone();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const emptyFile = new File([], "empty.csv", { type: "text/csv" });

    fireEvent.change(input, { target: { files: [emptyFile] } });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("File is empty");
  });

  it("rejects oversized files with a size message", () => {
    const { onFile } = renderDropZone({ maxSizeBytes: 1024 });
    const zone = getZone();
    const bigFile = new File(["x".repeat(2048)], "big.csv", {
      type: "text/csv",
    });

    fireEvent.drop(zone, { dataTransfer: { files: [bigFile] } });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("too large");
  });

  it("accepts files at the exact size limit", () => {
    const { onFile } = renderDropZone({ maxSizeBytes: 100 });
    const zone = getZone();
    const file = new File(["x".repeat(100)], "exact.csv", {
      type: "text/csv",
    });

    fireEvent.drop(zone, { dataTransfer: { files: [file] } });
    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("rejects non-CSV files on input change", () => {
    const { onFile, container } = renderDropZone();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const txtFile = new File(["hello"], "readme.txt", { type: "text/plain" });

    fireEvent.change(input, { target: { files: [txtFile] } });
    expect(onFile).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Only .csv files are accepted",
    );
  });
});
