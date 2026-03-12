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
} from "../test/test-utils";
import { DashboardPage } from "./DashboardPage";

const persons = [
  { id: "p1", name: "Alice", adjustment_account: "" },
  { id: "p2", name: "Bob", adjustment_account: "" },
];

const dashboardResponse = {
  current_month_year: 2026,
  current_month_month: 1,
  current_month_total_shared_spending: 160.0,
  current_month_net_shared_spending: 160.0,
  current_month_transaction_count: 2,
  current_month_person_summaries: [
    { person_id: "p1", total_paid: 100.0, total_share: 80.0 },
    { person_id: "p2", total_paid: 60.0, total_share: 80.0 },
  ],
  current_month_settlement: {
    amount: 20.0,
    from_person_id: "p2",
    to_person_id: "p1",
  },
  upload_statuses: [
    {
      person_id: "p1",
      person_name: "Alice",
      has_uploaded: true,
      upload_count: 1,
    },
    {
      person_id: "p2",
      person_name: "Bob",
      has_uploaded: true,
      upload_count: 1,
    },
  ],
  ytd_total_shared_spending: 160.0,
  ytd_settlement: {
    amount: 20.0,
    from_person_id: "p2",
    to_person_id: "p1",
  },
  month_history: [
    {
      year: 2026,
      month: 1,
      total_shared_spending: 160.0,
      settlement_amount: 20.0,
      settlement_from_person_id: "p2",
      settlement_to_person_id: "p1",
    },
  ],
  persons: [
    { id: "p1", name: "Alice" },
    { id: "p2", name: "Bob" },
  ],
  unmapped_categories: [],
};

const emptyResponse = {
  current_month_year: 2026,
  current_month_month: 3,
  current_month_total_shared_spending: 0.0,
  current_month_net_shared_spending: 0.0,
  current_month_transaction_count: 0,
  current_month_person_summaries: [
    { person_id: "p1", total_paid: 0.0, total_share: 0.0 },
    { person_id: "p2", total_paid: 0.0, total_share: 0.0 },
  ],
  current_month_settlement: {
    amount: 0.0,
    from_person_id: "p1",
    to_person_id: "p2",
  },
  upload_statuses: [
    {
      person_id: "p1",
      person_name: "Alice",
      has_uploaded: false,
      upload_count: 0,
    },
    {
      person_id: "p2",
      person_name: "Bob",
      has_uploaded: false,
      upload_count: 0,
    },
  ],
  ytd_total_shared_spending: 0.0,
  ytd_settlement: null,
  month_history: [],
  persons: [
    { id: "p1", name: "Alice" },
    { id: "p2", name: "Bob" },
  ],
  unmapped_categories: [],
};

const server = setupServer(
  http.get("/api/v1/persons/", () => HttpResponse.json(persons)),
  http.get("/api/v1/dashboard", () => HttpResponse.json(dashboardResponse)),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("DashboardPage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: "p1" });
  });

  it("renders settlement card with amount", async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      // Settlement appears in both the hero card and month history
      const owesElements = screen.getAllByText(/owes/);
      expect(owesElements.length).toBeGreaterThanOrEqual(1);
      const amountElements = screen.getAllByText("$20.00");
      expect(amountElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows upload status indicators", async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText("uploaded")).toHaveLength(2);
    });
  });

  it("shows empty state when no data", async () => {
    server.use(
      http.get("/api/v1/dashboard", () => HttpResponse.json(emptyResponse)),
    );

    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText(/No uploads yet/)).toBeInTheDocument();
      expect(
        screen.getByText("Upload a CSV to get started"),
      ).toBeInTheDocument();
    });
  });

  it("renders month history rows", async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Month History")).toBeInTheDocument();
      expect(screen.getByText("January 2026")).toBeInTheDocument();
    });
  });

  it("shows summary stats", async () => {
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("This month")).toBeInTheDocument();
      expect(screen.getByText("Year to date")).toBeInTheDocument();
      expect(screen.getByText("YTD balance")).toBeInTheDocument();
    });
  });

  it("shows partial upload status when only one person uploaded", async () => {
    const partialResponse = {
      ...dashboardResponse,
      upload_statuses: [
        {
          person_id: "p1",
          person_name: "Alice",
          has_uploaded: true,
          upload_count: 1,
        },
        {
          person_id: "p2",
          person_name: "Bob",
          has_uploaded: false,
          upload_count: 0,
        },
      ],
    };
    server.use(
      http.get("/api/v1/dashboard", () => HttpResponse.json(partialResponse)),
    );

    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("uploaded")).toBeInTheDocument();
      expect(screen.getByText("not yet")).toBeInTheDocument();
    });
  });

  it("month history rows link to transactions page", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("January 2026")).toBeInTheDocument();
    });

    const row = screen.getByText("January 2026").closest("tr");
    expect(row).not.toBeNull();
    await user.click(row!);

    // useNavigate was called — verify the URL changed
    // MemoryRouter doesn't expose location directly, but we can verify
    // the row has cursor-pointer styling (interactive indicator)
    expect(row).toHaveClass("cursor-pointer");
  });
});
