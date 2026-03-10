import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
} from "vitest";
import { useIdentityStore } from "@/lib/identity";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/test/test-utils";
import { Sidebar } from "./Sidebar";

const persons = [
  { id: "p1", name: "Alice", adjustment_account: "adj-1" },
  { id: "p2", name: "Bob", adjustment_account: "adj-2" },
];

const server = setupServer(
  http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("Sidebar", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: "p1" });
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

  it("disables Dashboard, Transactions, and Budget", () => {
    renderWithProviders(<Sidebar />, {
      routerProps: { initialEntries: ["/upload"] },
    });
    expect(screen.getByText("Dashboard").closest("span")).toHaveClass(
      "cursor-not-allowed",
    );
    expect(screen.getByText("Transactions").closest("span")).toHaveClass(
      "cursor-not-allowed",
    );
    expect(screen.getByText("Budget").closest("span")).toHaveClass(
      "cursor-not-allowed",
    );
  });

  it("enables Upload and Settings as links", () => {
    renderWithProviders(<Sidebar />, {
      routerProps: { initialEntries: ["/upload"] },
    });
    expect(screen.getByRole("link", { name: "Upload" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
  });

  it("displays both person names in identity toggle", async () => {
    renderWithProviders(<Sidebar />, {
      routerProps: { initialEntries: ["/upload"] },
    });
    await waitFor(() => {
      expect(screen.getByText("Alice")).toBeInTheDocument();
    });
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("switches identity when clicking the inactive person", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Sidebar />, {
      routerProps: { initialEntries: ["/upload"] },
    });

    await waitFor(() => {
      expect(screen.getByText("Bob")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Bob"));
    expect(useIdentityStore.getState().currentPersonId).toBe("p2");
  });
});
