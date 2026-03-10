import { beforeEach, describe, expect, it } from "vitest";
import { useIdentityStore } from "@/lib/identity";
import { renderWithProviders, screen, userEvent } from "@/test/test-utils";
import { ProfilePicker } from "./ProfilePicker";

const persons = [
  { id: "p1", name: "Alice", adjustment_account: "adj-1" },
  { id: "p2", name: "Bob", adjustment_account: "adj-2" },
];

describe("ProfilePicker", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: null });
  });

  it("renders both person names", () => {
    renderWithProviders(<ProfilePicker persons={persons} />);
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("renders person initials", () => {
    renderWithProviders(<ProfilePicker persons={persons} />);
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
  });

  it("shows heading", () => {
    renderWithProviders(<ProfilePicker persons={persons} />);
    expect(screen.getByText("Who are you?")).toBeInTheDocument();
  });

  it("sets identity when a person card is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfilePicker persons={persons} />);

    await user.click(screen.getByText("Alice"));
    expect(useIdentityStore.getState().currentPersonId).toBe("p1");
  });

  it("sets identity for the second person", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfilePicker persons={persons} />);

    await user.click(screen.getByText("Bob"));
    expect(useIdentityStore.getState().currentPersonId).toBe("p2");
  });
});
