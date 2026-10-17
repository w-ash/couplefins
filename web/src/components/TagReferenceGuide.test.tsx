import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/test/test-utils";
import { TagReferenceGuide } from "./TagReferenceGuide";

describe("TagReferenceGuide", () => {
  it("documents the Labels group", async () => {
    renderWithProviders(<TagReferenceGuide />);
    await userEvent.click(screen.getByRole("button"));

    expect(screen.getByRole("heading", { name: "Labels" })).toBeInTheDocument();
    for (const tag of ["line:mortgage", "pot:renovation", "loan:<slug>"]) {
      expect(screen.getByText(tag)).toBeInTheDocument();
    }
    expect(screen.getByText(/Labels never change a split/)).toHaveTextContent(
      "An import never removes a label",
    );
  });
});
