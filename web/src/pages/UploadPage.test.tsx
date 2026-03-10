import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "../test/test-utils";
import { UploadPage } from "./UploadPage";

describe("UploadPage", () => {
  it("renders the upload form", () => {
    renderWithProviders(<UploadPage />);
    expect(screen.getByText("Upload Transactions")).toBeInTheDocument();
    expect(screen.getByLabelText("Who are you?")).toBeInTheDocument();
    expect(screen.getByLabelText("Month")).toBeInTheDocument();
    expect(screen.getByLabelText("Year")).toBeInTheDocument();
    expect(screen.getByLabelText("Monarch CSV")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview" })).toBeInTheDocument();
  });

  it("disables preview button when no person selected", () => {
    renderWithProviders(<UploadPage />);
    const button = screen.getByRole("button", { name: "Preview" });
    expect(button).toBeDisabled();
  });
});
