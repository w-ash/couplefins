import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "../test/test-utils";
import { SetupPage } from "./SetupPage";

const server = setupServer();

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("SetupPage", () => {
  it("renders the setup form with two name inputs", () => {
    renderWithProviders(<SetupPage />);
    expect(screen.getByText("Welcome to Couplefins")).toBeInTheDocument();
    expect(screen.getByLabelText("Person 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Person 2")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Get Started" }),
    ).toBeInTheDocument();
  });

  it("disables submit when names are empty", () => {
    renderWithProviders(<SetupPage />);
    expect(screen.getByRole("button", { name: "Get Started" })).toBeDisabled();
  });

  it("enables submit when both names are filled", async () => {
    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    await user.type(screen.getByLabelText("Person 2"), "Bob");

    expect(screen.getByRole("button", { name: "Get Started" })).toBeEnabled();
  });

  it("warns when both names match", async () => {
    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    await user.type(screen.getByLabelText("Person 2"), "Alice");

    expect(
      screen.getByText("Both names are the same — are you sure?"),
    ).toBeInTheDocument();
  });

  it("submits both names to the API", async () => {
    const createdNames: string[] = [];
    server.use(
      http.post("/api/v1/persons/", async ({ request }) => {
        const body = (await request.json()) as { name: string };
        createdNames.push(body.name);
        return HttpResponse.json(
          { id: crypto.randomUUID(), name: body.name, adjustment_account: "" },
          { status: 201 },
        );
      }),
    );

    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    await user.type(screen.getByLabelText("Person 2"), "Bob");
    await user.click(screen.getByRole("button", { name: "Get Started" }));

    await waitFor(() => {
      expect(createdNames).toEqual(["Alice", "Bob"]);
    });
  });

  it("shows error on API failure", async () => {
    server.use(
      http.post("/api/v1/persons/", () => {
        return HttpResponse.json(
          { detail: "Name is required" },
          { status: 400 },
        );
      }),
    );

    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    await user.type(screen.getByLabelText("Person 2"), "Bob");
    await user.click(screen.getByRole("button", { name: "Get Started" }));

    await waitFor(() => {
      expect(screen.getByText("Name is required")).toBeInTheDocument();
    });
  });
});
