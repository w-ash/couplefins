import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import {
  makeEmptySpendingTrends,
  makeSpendingTrends,
} from "@/test/insights-fixtures";
import { server } from "@/test/server";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/test/test-utils";
import { InsightsPage } from "./InsightsPage";

const emptyResponse = makeEmptySpendingTrends();
const populatedResponse = makeSpendingTrends();

function servePopulated() {
  server.use(
    http.get("/api/v1/insights/spending-trends", () =>
      HttpResponse.json(populatedResponse),
    ),
  );
}

async function renderPopulated(path = "/?year=2026&month=2") {
  servePopulated();
  const view = renderWithProviders(<InsightsPage />, {
    routerProps: { initialEntries: [path] },
  });
  await waitFor(() => {
    expect(screen.getByTestId("group-breakdown")).toBeInTheDocument();
  });
  return view;
}

describe("InsightsPage", () => {
  beforeEach(() => {
    server.use(
      http.get("/api/v1/insights/spending-trends", () =>
        HttpResponse.json(emptyResponse),
      ),
    );
  });

  it("renders the heading, month picker, and controls", () => {
    renderWithProviders(<InsightsPage />);
    expect(
      screen.getByRole("heading", { name: "Insights" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Select month")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Household" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Month" })).toBeChecked();
  });

  it("takes the month from the response when the URL names none", async () => {
    let requested: URLSearchParams | undefined;
    server.use(
      http.get("/api/v1/insights/spending-trends", ({ request }) => {
        requested = new URL(request.url).searchParams;
        return HttpResponse.json(populatedResponse);
      }),
    );

    renderWithProviders(<InsightsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Select month" }),
      ).toHaveTextContent("February 2026");
    });
    // The period must be omitted, never sent as "null".
    expect(requested?.has("year")).toBe(false);
    expect(requested?.has("month")).toBe(false);
    expect(requested?.has("comparison_year")).toBe(false);
  });

  it("sends the URL's period and lets the server pick the comparison year", async () => {
    let requested: URLSearchParams | undefined;
    server.use(
      http.get("/api/v1/insights/spending-trends", ({ request }) => {
        requested = new URL(request.url).searchParams;
        return HttpResponse.json(populatedResponse);
      }),
    );

    renderWithProviders(<InsightsPage />, {
      routerProps: { initialEntries: ["/?year=2026&month=2"] },
    });

    await waitFor(() => {
      expect(screen.getByTestId("group-breakdown")).toBeInTheDocument();
    });
    expect(requested?.get("year")).toBe("2026");
    expect(requested?.get("month")).toBe("2");
    // The "compare against year - 1" rule lives in the use case alone.
    expect(requested?.has("comparison_year")).toBe(false);
  });

  it("leaves the month picker inert until the month is known", async () => {
    renderWithProviders(<InsightsPage />);

    expect(screen.getByRole("button", { name: "Select month" })).toBeDisabled();
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Select month" }),
      ).toBeEnabled();
    });
  });

  it("shows a month named by the URL alone straight away", async () => {
    // year and month are read independently, so a shared link naming only
    // the month already determines what the picker will show.
    renderWithProviders(<InsightsPage />, {
      routerProps: { initialEntries: ["/?month=5"] },
    });

    const trigger = screen.getByRole("button", { name: "Select month" });
    expect(trigger).toBeEnabled();
    expect(trigger).toHaveTextContent("May");
  });

  it("shows the empty state when the year has no data", async () => {
    renderWithProviders(<InsightsPage />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "No spending data" }),
      ).toBeInTheDocument();
    });
  });

  it("shows the period total with a comparison sentence", async () => {
    await renderPopulated();
    expect(screen.getByText("$650.00")).toBeInTheDocument();
    expect(screen.getByText("$50.00 less than January")).toBeInTheDocument();
    expect(screen.getByTestId("ytd-mini-chart")).toBeInTheDocument();
  });

  it("defaults to the flow chart and lists groups in the breakdown table", async () => {
    await renderPopulated();
    expect(screen.getByTestId("spending-flow-chart")).toBeInTheDocument();
    const table = within(screen.getByTestId("group-breakdown"));
    expect(table.getByText("Food & Dining")).toBeInTheDocument();
    expect(table.getByText("$450.00")).toBeInTheDocument();
    expect(table.getByText("+13%")).toBeInTheDocument();
    expect(
      table.getByRole("link", { name: "View Food & Dining transactions" }),
    ).toHaveAttribute(
      "href",
      "/transactions?year=2026&month=2&scope=household&cat=Dining+Out&cat=Groceries",
    );
  });

  it("expands a group row into linked categories", async () => {
    await renderPopulated();
    const table = within(screen.getByTestId("group-breakdown"));
    await userEvent.click(table.getByRole("button", { name: /Food & Dining/ }));
    const groceries = table.getByRole("link", { name: /Groceries/ });
    expect(groceries).toHaveAttribute(
      "href",
      "/transactions?year=2026&month=2&scope=household&cat=Groceries",
    );
    expect(table.getByText("$150.00")).toBeInTheDocument();
  });

  it("switches to year to date and links with a date range", async () => {
    await renderPopulated("/?year=2026&month=2&period=ytd");
    expect(screen.getByText("Jan–Feb 2026")).toBeInTheDocument();
    expect(screen.getByText("$1,350.00")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "View Travel transactions" }),
    ).toHaveAttribute(
      "href",
      "/transactions?startDate=2026-01-01&endDate=2026-02-28&scope=household&cat=Flights",
    );
    expect(screen.queryByText(/Notable in/)).not.toBeInTheDocument();
  });

  it("shows the donut with a legend that drills into a group", async () => {
    await renderPopulated("/?year=2026&month=2&chart=donut");
    expect(screen.getByTestId("spending-donut")).toBeInTheDocument();
    const legend = within(screen.getByTestId("spending-legend"));
    expect(legend.getByText("Travel")).toBeInTheDocument();
    await userEvent.click(
      legend.getByRole("button", { name: /Food & Dining/ }),
    );
    expect(
      screen.getByRole("navigation", { name: "Breakdown level" }),
    ).toHaveTextContent("All groups");
    expect(legend.getByRole("link", { name: /Dining Out/ })).toHaveAttribute(
      "href",
      "/transactions?year=2026&month=2&scope=household&cat=Dining+Out",
    );
    await userEvent.click(screen.getByRole("button", { name: "All groups" }));
    expect(legend.getByText("Travel")).toBeInTheDocument();
  });

  it("shows merchant bars with search links", async () => {
    await renderPopulated("/?year=2026&month=2&chart=bars&by=merchant");
    const bars = within(screen.getByTestId("spending-bars"));
    expect(bars.getByRole("link", { name: /Sushi Place/ })).toHaveAttribute(
      "href",
      "/transactions?year=2026&month=2&scope=household&q=Sushi+Place",
    );
  });

  it("lists what moved this month with links", async () => {
    await renderPopulated();
    const list = within(screen.getByTestId("notable-list"));
    expect(
      list.getByRole("link", { name: /Dining Out up 20%/ }),
    ).toHaveAttribute(
      "href",
      "/transactions?year=2026&month=2&scope=household&cat=Dining+Out",
    );
    expect(list.getByText("Groceries is new this month")).toBeInTheDocument();
  });

  it("sends the scope from the URL and carries it into every link", async () => {
    let requestedScope: string | null = null;
    server.use(
      http.get("/api/v1/insights/spending-trends", ({ request }) => {
        requestedScope = new URL(request.url).searchParams.get("scope");
        return HttpResponse.json(populatedResponse);
      }),
    );
    renderWithProviders(<InsightsPage />, {
      routerProps: { initialEntries: ["/?year=2026&month=2&scope=personal"] },
    });
    await waitFor(() => {
      expect(requestedScope).toBe("personal");
    });
    expect(screen.getByRole("radio", { name: "My Spending" })).toBeChecked();
    expect(
      screen.getByText(/Your share of household spending/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "View Travel transactions" }),
    ).toHaveAttribute(
      "href",
      "/transactions?year=2026&month=2&scope=personal&cat=Flights",
    );
  });

  it("explains an empty month inside a year with data", async () => {
    server.use(
      http.get("/api/v1/insights/spending-trends", () =>
        HttpResponse.json({
          ...populatedResponse,
          month: 3,
          month_flow: {
            cells: [],
            top_merchants: [],
            largest_transactions: [],
          },
        }),
      ),
    );
    renderWithProviders(<InsightsPage />, {
      routerProps: { initialEntries: ["/?year=2026&month=3"] },
    });
    await waitFor(() => {
      expect(screen.getByText(/No spending in March 2026/)).toBeInTheDocument();
    });
  });

  it("shows the error state", async () => {
    server.use(
      http.get("/api/v1/insights/spending-trends", () =>
        HttpResponse.json(
          { error: { code: "SERVER_ERROR", message: "Something broke" } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<InsightsPage />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
