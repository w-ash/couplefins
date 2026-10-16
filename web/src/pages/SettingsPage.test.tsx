import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "@/test/server";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/test/test-utils";
import { SettingsPage } from "./SettingsPage";

const persons = [
  {
    id: "p1",
    name: "Alice",
    adjustment_account: "Alice Adj",
    theme_preference: "system",
    chat_voice: "fiona",
  },
  {
    id: "p2",
    name: "Bob",
    adjustment_account: "",
    theme_preference: "system",
    chat_voice: "fiona",
  },
];

const accounts = {
  accounts: [
    {
      id: "a1",
      name: "Joint Checking",
      kind: "personal",
      owner_person_id: "p1",
    },
    {
      id: "a2",
      name: "Joint Checking",
      kind: "personal",
      owner_person_id: "p2",
    },
    { id: "a3", name: "Alice Visa", kind: "personal", owner_person_id: "p1" },
    { id: "a4", name: "Household Pool", kind: "joint", owner_person_id: null },
  ],
};

const healthResponse = {
  status: "ok",
  database_host: "localhost",
  database_mode: "Local PostgreSQL",
};

describe("SettingsPage", () => {
  beforeEach(() => {
    server.use(
      http.get("/api/v1/category-groups", () => HttpResponse.json([])),
      http.get("/api/v1/category-mappings/unmapped", () =>
        HttpResponse.json([]),
      ),
      http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
      http.get("/api/v1/health", () => HttpResponse.json(healthResponse)),
      http.get("/api/v1/settings/settlement-merchants", () =>
        HttpResponse.json([]),
      ),
      http.get("/api/v1/settings/accounts", () => HttpResponse.json(accounts)),
    );
  });
  it("renders the settings heading", () => {
    renderWithProviders(<SettingsPage />);
    expect(
      screen.getByRole("heading", { name: "Settings" }),
    ).toBeInTheDocument();
  });

  it("renders the category groups section", () => {
    renderWithProviders(<SettingsPage />);
    expect(
      screen.getByRole("heading", { name: "Category Groups" }),
    ).toBeInTheDocument();
  });

  it("renders the people section with adjustment account settings", async () => {
    renderWithProviders(<SettingsPage />);
    expect(screen.getByRole("heading", { name: "People" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText("Alice").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Bob").length).toBeGreaterThan(0);
    });
  });

  it("has aria-labelledby on each section", async () => {
    renderWithProviders(<SettingsPage />);

    await waitFor(() => {
      const sections = screen.getAllByRole("region");
      expect(sections).toHaveLength(5);

      expect(sections[0]).toHaveAttribute(
        "aria-labelledby",
        "settings-category-mappings",
      );
      expect(sections[1]).toHaveAttribute("aria-labelledby", "settings-people");
      expect(sections[2]).toHaveAttribute(
        "aria-labelledby",
        "settings-accounts",
      );
      expect(sections[3]).toHaveAttribute(
        "aria-labelledby",
        "settings-settlement-merchants",
      );
      expect(sections[4]).toHaveAttribute("aria-labelledby", "settings-system");
    });
  });

  it("shows empty state when no categories exist", async () => {
    renderWithProviders(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/No categories yet/)).toBeInTheDocument();
    });

    expect(screen.getByText("Upload a CSV")).toBeInTheDocument();
  });

  it("shows database info in system section", async () => {
    renderWithProviders(<SettingsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "System" }),
      ).toBeInTheDocument();
      expect(screen.getByText("Local PostgreSQL")).toBeInTheDocument();
      expect(screen.getByText("localhost")).toBeInTheDocument();
    });
  });

  describe("accounts", () => {
    async function accountsSection() {
      const heading = await screen.findByRole("heading", { name: "Accounts" });
      const section = heading.closest("section");
      if (!section) throw new Error("accounts section not found");
      return within(section);
    }

    it("groups account labels and shows owners or the joint mark", async () => {
      renderWithProviders(<SettingsPage />);
      const section = await accountsSection();

      expect(await section.findByText("Joint Checking")).toBeInTheDocument();
      const row = (name: string) => {
        const li = section.getByText(name).closest("li");
        if (!li) throw new Error(`row for ${name} not found`);
        return within(li);
      };
      // One row per label, with both uploaders.
      expect(section.getAllByText("Joint Checking")).toHaveLength(1);
      expect(row("Joint Checking").getByText("Alice")).toBeInTheDocument();
      expect(row("Joint Checking").getByText("Bob")).toBeInTheDocument();
      expect(
        row("Joint Checking").getByRole("button", { name: /Mark joint/ }),
      ).toBeInTheDocument();
      expect(row("Household Pool").getByText("Joint")).toBeInTheDocument();
      expect(
        row("Household Pool").getByRole("button", { name: /Unmark/ }),
      ).toBeInTheDocument();
    });

    it("marks a label joint after confirmation", async () => {
      let body: unknown;
      server.use(
        http.post("/api/v1/settings/accounts/joint", async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(accounts);
        }),
      );
      renderWithProviders(<SettingsPage />);
      const section = await accountsSection();

      await userEvent.click(
        await section.findByRole("button", {
          name: "Mark joint Joint Checking",
        }),
      );
      const dialog = await screen.findByRole("dialog");
      expect(dialog).toHaveTextContent(/move out of settlement/);
      expect(dialog).toHaveTextContent(/collapse to one/);
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Mark joint" }),
      );

      await waitFor(() => expect(body).toEqual({ label: "Joint Checking" }));
    });

    it("shows the refusal when the month is finalized", async () => {
      server.use(
        http.post("/api/v1/settings/accounts/joint", () =>
          HttpResponse.json(
            { error: { code: "FINALIZED", message: "January is finalized" } },
            { status: 409 },
          ),
        ),
      );
      renderWithProviders(<SettingsPage />);
      const section = await accountsSection();

      await userEvent.click(
        await section.findByRole("button", {
          name: "Mark joint Joint Checking",
        }),
      );
      const dialog = await screen.findByRole("dialog");
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Mark joint" }),
      );

      expect(
        await within(dialog).findByText("January is finalized"),
      ).toBeVisible();
    });

    it("unmarks a joint label", async () => {
      let url = "";
      server.use(
        http.delete("/api/v1/settings/accounts/joint/:label", ({ request }) => {
          url = new URL(request.url).pathname;
          return HttpResponse.json(accounts);
        }),
      );
      renderWithProviders(<SettingsPage />);
      const section = await accountsSection();

      await userEvent.click(
        await section.findByRole("button", { name: "Unmark Household Pool" }),
      );
      const dialog = await screen.findByRole("dialog");
      expect(dialog).toHaveTextContent(/back to the partner who uploaded/);
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Unmark" }),
      );

      await waitFor(() =>
        expect(url).toBe("/api/v1/settings/accounts/joint/Household%20Pool"),
      );
    });

    it("encodes a label with a space and # in the unmark URL", async () => {
      let rawUrl = "";
      server.use(
        http.get("/api/v1/settings/accounts", () =>
          HttpResponse.json({
            accounts: [
              {
                id: "a9",
                name: "Pool #2",
                kind: "joint",
                owner_person_id: null,
              },
            ],
          }),
        ),
        http.delete("/api/v1/settings/accounts/joint/:label", ({ request }) => {
          rawUrl = request.url;
          return HttpResponse.json(accounts);
        }),
      );
      renderWithProviders(<SettingsPage />);
      const section = await accountsSection();

      await userEvent.click(
        await section.findByRole("button", { name: "Unmark Pool #2" }),
      );
      const dialog = await screen.findByRole("dialog");
      await userEvent.click(
        within(dialog).getByRole("button", { name: "Unmark" }),
      );

      await waitFor(() =>
        expect(new URL(rawUrl).pathname).toBe(
          "/api/v1/settings/accounts/joint/Pool%20%232",
        ),
      );
    });
  });
});
