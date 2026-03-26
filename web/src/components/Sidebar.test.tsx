import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { useIdentityStore } from "@/lib/identity";
import { server } from "@/test/server";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/test/test-utils";
import { Sidebar } from "./Sidebar";

describe("Sidebar", () => {
  beforeEach(() => {
    useIdentityStore.setState({
      currentPersonId: "p1",
      currentPersonName: "Alice",
    });
    server.use(
      http.post("/api/v1/auth/logout", () => HttpResponse.json({ ok: true })),
    );
  });

  it("renders the wordmark", async () => {
    renderWithProviders(<Sidebar />, {
      routerProps: { initialEntries: ["/upload"] },
    });
    expect(screen.getByText("CoupleFins")).toBeInTheDocument();
  });

  it("renders all nav items", async () => {
    renderWithProviders(<Sidebar />, {
      routerProps: { initialEntries: ["/upload"] },
    });
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Transactions")).toBeInTheDocument();
    expect(screen.getByText("Budget")).toBeInTheDocument();
    expect(screen.getByText("Upload")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("enables all nav items as links", () => {
    renderWithProviders(<Sidebar />, {
      routerProps: { initialEntries: ["/upload"] },
    });
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Transactions" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Budget" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
  });

  it("displays the current person name", () => {
    renderWithProviders(<Sidebar />, {
      routerProps: { initialEntries: ["/upload"] },
    });
    expect(screen.getByText("Alice")).toBeInTheDocument();
  });

  it("has a logout button", () => {
    renderWithProviders(<Sidebar />, {
      routerProps: { initialEntries: ["/upload"] },
    });
    expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
  });

  it("clears identity on logout", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Sidebar />, {
      routerProps: { initialEntries: ["/upload"] },
    });

    await user.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => {
      expect(useIdentityStore.getState().currentPersonId).toBeNull();
      expect(useIdentityStore.getState().currentPersonName).toBeNull();
    });
  });

  it("has aria-label on aside and nav", () => {
    renderWithProviders(<Sidebar />, {
      routerProps: { initialEntries: ["/upload"] },
    });
    expect(
      screen.getByRole("complementary", { name: "Main navigation" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "App navigation" }),
    ).toBeInTheDocument();
  });
});
