import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "@/test/server";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "../test/test-utils";
import { SetupPage } from "./SetupPage";

const VALID_PASSWORD = "password123";

describe("SetupPage", () => {
  it("renders the setup form with name and password inputs", () => {
    renderWithProviders(<SetupPage />);
    expect(screen.getByText("Welcome to CoupleFins")).toBeInTheDocument();
    expect(screen.getByLabelText("Person 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Person 2")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Password")).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "Get Started" }),
    ).toBeInTheDocument();
  });

  it("disables submit when names are empty", () => {
    renderWithProviders(<SetupPage />);
    expect(screen.getByRole("button", { name: "Get Started" })).toBeDisabled();
  });

  it("disables submit when names are filled but passwords are missing", async () => {
    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    await user.type(screen.getByLabelText("Person 2"), "Bob");

    expect(screen.getByRole("button", { name: "Get Started" })).toBeDisabled();
  });

  it("enables submit when both names and valid passwords are filled", async () => {
    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    // After typing name1, the password label becomes "Alice's password"
    await user.type(screen.getByLabelText("Alice's password"), VALID_PASSWORD);
    await user.type(screen.getByLabelText("Person 2"), "Bob");
    await user.type(screen.getByLabelText("Bob's password"), VALID_PASSWORD);

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

  it("submits names and passwords to the API in a single request", async () => {
    let capturedBody: {
      name1: string;
      name2: string;
      password1: string;
      password2: string;
    } | null = null;
    server.use(
      http.post("/api/v1/persons/setup", async ({ request }) => {
        capturedBody = (await request.json()) as {
          name1: string;
          name2: string;
          password1: string;
          password2: string;
        };
        return HttpResponse.json(
          [
            {
              id: crypto.randomUUID(),
              name: capturedBody.name1,
              adjustment_account: "",
            },
            {
              id: crypto.randomUUID(),
              name: capturedBody.name2,
              adjustment_account: "",
            },
          ],
          { status: 201 },
        );
      }),
    );

    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    await user.type(screen.getByLabelText("Alice's password"), VALID_PASSWORD);
    await user.type(screen.getByLabelText("Person 2"), "Bob");
    await user.type(screen.getByLabelText("Bob's password"), VALID_PASSWORD);
    await user.click(screen.getByRole("button", { name: "Get Started" }));

    await waitFor(() => {
      expect(capturedBody).toEqual({
        name1: "Alice",
        name2: "Bob",
        password1: VALID_PASSWORD,
        password2: VALID_PASSWORD,
      });
    });
  });

  it("shows error on API failure", async () => {
    server.use(
      http.post("/api/v1/persons/setup", () => {
        return HttpResponse.json(
          { error: { code: "VALIDATION_ERROR", message: "Name is required" } },
          { status: 422 },
        );
      }),
    );

    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    await user.type(screen.getByLabelText("Alice's password"), VALID_PASSWORD);
    await user.type(screen.getByLabelText("Person 2"), "Bob");
    await user.type(screen.getByLabelText("Bob's password"), VALID_PASSWORD);
    await user.click(screen.getByRole("button", { name: "Get Started" }));

    await waitFor(() => {
      expect(screen.getByText("Name is required")).toBeInTheDocument();
    });
  });

  it("shows warning with role=alert when names match", async () => {
    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    await user.type(screen.getByLabelText("Person 2"), "Alice");

    const warning = screen.getByRole("alert");
    expect(warning).toHaveTextContent(
      "Both names are the same — are you sure?",
    );
  });

  it("shows error with role=alert on API failure", async () => {
    server.use(
      http.post("/api/v1/persons/setup", () => {
        return HttpResponse.json(
          { error: { code: "VALIDATION_ERROR", message: "Name is required" } },
          { status: 422 },
        );
      }),
    );

    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    await user.type(screen.getByLabelText("Alice's password"), VALID_PASSWORD);
    await user.type(screen.getByLabelText("Person 2"), "Bob");
    await user.type(screen.getByLabelText("Bob's password"), VALID_PASSWORD);
    await user.click(screen.getByRole("button", { name: "Get Started" }));

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent("Name is required");
    });
  });
});
