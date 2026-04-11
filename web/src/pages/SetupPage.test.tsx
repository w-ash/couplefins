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

async function fillForm(
  user: ReturnType<typeof userEvent.setup>,
  { pw1 = VALID_PASSWORD, pw2 = VALID_PASSWORD } = {},
) {
  await user.type(screen.getByLabelText("Person 1"), "Alice");
  await user.type(screen.getByLabelText("Alice's password"), pw1);
  await user.type(screen.getAllByLabelText("Confirm password")[0], pw1);
  await user.type(screen.getByLabelText("Person 2"), "Bob");
  await user.type(screen.getByLabelText("Bob's password"), pw2);
  await user.type(screen.getAllByLabelText("Confirm password")[1], pw2);
}

describe("SetupPage", () => {
  it("renders the setup form with name, password, and confirm inputs", () => {
    renderWithProviders(<SetupPage />);
    expect(screen.getByText("Welcome to CoupleFins")).toBeInTheDocument();
    expect(screen.getByLabelText("Person 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Person 2")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Password")).toHaveLength(2);
    expect(screen.getAllByLabelText("Confirm password")).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "Get Started" }),
    ).toBeInTheDocument();
  });

  it("disables submit when names are empty", () => {
    renderWithProviders(<SetupPage />);
    expect(screen.getByRole("button", { name: "Get Started" })).toBeDisabled();
  });

  it("disables submit when passwords are missing", async () => {
    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    await user.type(screen.getByLabelText("Person 2"), "Bob");

    expect(screen.getByRole("button", { name: "Get Started" })).toBeDisabled();
  });

  it("disables submit when confirm passwords don't match", async () => {
    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Person 1"), "Alice");
    await user.type(screen.getByLabelText("Alice's password"), VALID_PASSWORD);
    await user.type(
      screen.getAllByLabelText("Confirm password")[0],
      "different",
    );
    await user.type(screen.getByLabelText("Person 2"), "Bob");
    await user.type(screen.getByLabelText("Bob's password"), VALID_PASSWORD);
    await user.type(
      screen.getAllByLabelText("Confirm password")[1],
      VALID_PASSWORD,
    );

    expect(screen.getByRole("button", { name: "Get Started" })).toBeDisabled();
  });

  it("enables submit when names, passwords, and confirms are valid", async () => {
    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();
    await fillForm(user);

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
    let capturedBody: Record<string, string> | null = null;
    server.use(
      http.post("/api/v1/persons/setup", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, string>;
        return HttpResponse.json(
          [
            {
              id: crypto.randomUUID(),
              name: capturedBody.name1,
              adjustment_account: "",
              theme_preference: "system",
              chat_voice: "fiona",
            },
            {
              id: crypto.randomUUID(),
              name: capturedBody.name2,
              adjustment_account: "",
              theme_preference: "system",
              chat_voice: "fiona",
            },
          ],
          { status: 201 },
        );
      }),
    );

    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();
    await fillForm(user);
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
    await fillForm(user);
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
    await fillForm(user);
    await user.click(screen.getByRole("button", { name: "Get Started" }));

    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent("Name is required");
    });
  });

  it("toggles password visibility", async () => {
    renderWithProviders(<SetupPage />);
    const user = userEvent.setup();

    const toggles = screen.getAllByRole("button", { name: "Show password" });
    expect(toggles).toHaveLength(4); // 2 passwords + 2 confirms

    const passwordInput = screen.getAllByLabelText("Password")[0];
    expect(passwordInput).toHaveAttribute("type", "password");

    await user.click(toggles[0]);
    expect(passwordInput).toHaveAttribute("type", "text");
    expect(toggles[0]).toHaveAttribute("aria-pressed", "true");

    await user.click(toggles[0]);
    expect(passwordInput).toHaveAttribute("type", "password");
    expect(toggles[0]).toHaveAttribute("aria-pressed", "false");
  });
});
