import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { HouseResponse } from "@/api/generated/model";
import { useIdentityStore } from "@/lib/identity";
import { ALICE_ID, BOB_ID, makeHouseResponse } from "@/test/house-fixtures";
import { server } from "@/test/server";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/test/test-utils";
import { HousePage } from "./HousePage";

function serveHouse(response: HouseResponse) {
  server.use(http.get("/api/v1/house", () => HttpResponse.json(response)));
}

function withExamples(sections: string[]): HouseResponse {
  return {
    ...makeHouseResponse(),
    example_sections: sections,
  } as HouseResponse;
}

describe("HousePage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: ALICE_ID });
    server.use(
      http.get("/api/v1/house/manual-entries", () => HttpResponse.json([])),
    );
  });

  it("shows the example notice only for example data", async () => {
    serveHouse(makeHouseResponse());
    const { unmount } = renderWithProviders(<HousePage />);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Example figures",
    );
    unmount();

    serveHouse(makeHouseResponse({ example_sections: [] }));
    renderWithProviders(<HousePage />);
    await screen.findByRole("heading", { name: "Put in" });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("marks only the sections named in example_sections", async () => {
    serveHouse(withExamples(["put_in", "loans"]));
    renderWithProviders(<HousePage />);
    await screen.findByRole("heading", { name: "Put in" });

    expect(screen.getByRole("status")).toHaveTextContent("Example figures");
    const pills = screen.getAllByText("Example");
    expect(pills).toHaveLength(2);
    const sectionOf = (pill: HTMLElement) =>
      pill.closest("section")?.getAttribute("aria-labelledby");
    expect(pills.map(sectionOf)).toEqual(["house-put-in", "house-loans"]);
  });

  it("shows no notice or pills once every section is real", async () => {
    serveHouse(withExamples([]));
    renderWithProviders(<HousePage />);
    await screen.findByRole("heading", { name: "Put in" });

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.queryByText("Example")).not.toBeInTheDocument();
  });

  it("renders the six sections", async () => {
    serveHouse(makeHouseResponse());
    renderWithProviders(<HousePage />);
    for (const name of [
      "Put in",
      "Shares",
      "Loans",
      "Upcoming",
      "Set aside",
      "Recent activity",
    ]) {
      expect(await screen.findByRole("heading", { name })).toBeInTheDocument();
    }
  });

  it("renders served figures", async () => {
    serveHouse(makeHouseResponse());
    renderWithProviders(<HousePage />);
    await screen.findByRole("heading", { name: "Put in" });

    expect(screen.getAllByText("$102,000.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Closing")).toBeInTheDocument();
    expect(screen.getByText("Repairs")).toBeInTheDocument();
    expect(screen.getByText("Deposits not yet spent")).toBeInTheDocument();
    expect(screen.getByText("Short by $450.00")).toBeInTheDocument();
    expect(screen.getAllByText("Tax reserve").length).toBeGreaterThan(0);
    expect(screen.getByText("estimate")).toBeInTheDocument();
    expect(screen.getByText("Deposit")).toBeInTheDocument();
    expect(screen.getByText("Alice $300.00 · Bob $0.00")).toBeInTheDocument();
    expect(screen.getByText("60.0%")).toBeInTheDocument();
    expect(screen.getByText("4.50%")).toBeInTheDocument();
    expect(screen.getAllByText("Joint checking")).toHaveLength(2);
  });

  it("renders real set-aside buckets, the unassigned one last and muted", async () => {
    serveHouse(
      withExamples(["put_in", "loans", "upcoming", "recent_activity"]),
    );
    renderWithProviders(<HousePage />);

    const heading = await screen.findByRole("heading", { name: "Set aside" });
    const section = heading.closest("section") as HTMLElement;
    expect(within(section).queryByText("Example")).not.toBeInTheDocument();
    const [buckets] = within(section).getAllByRole("table");
    const [, body] = within(buckets).getAllByRole("rowgroup");
    const rows = within(body).getAllByRole("row");
    const unassigned = rows[rows.length - 1];
    expect(unassigned).toHaveTextContent("Unassigned");
    expect(within(section).getAllByText("no pot tag")).toEqual([
      within(unassigned).getByText("no pot tag"),
    ]);
    expect(unassigned.firstElementChild).toHaveClass("text-muted-foreground");
    expect(rows[0].firstElementChild).not.toHaveClass("text-muted-foreground");
  });

  it("totals the buckets beside the bank balance and its difference", async () => {
    serveHouse(makeHouseResponse());
    renderWithProviders(<HousePage />);

    const heading = await screen.findByRole("heading", { name: "Set aside" });
    const section = heading.closest("section") as HTMLElement;
    expect(
      within(section).getByText("Total set aside").nextSibling,
    ).toHaveTextContent("$3,590.00");
    expect(
      within(section).getByText("Bank balance").nextSibling,
    ).toHaveTextContent("$3,640.00");
    expect(within(section).getByText(/as of/)).toBeInTheDocument();
    expect(
      within(section).getByText("Difference").nextSibling,
    ).toHaveTextContent("+$50.00");
  });

  it("shows a placeholder when no bank balance is entered", async () => {
    const base = makeHouseResponse();
    serveHouse({
      ...base,
      set_aside: {
        ...base.set_aside,
        bank_balance: null,
        bank_balance_as_of: null,
        difference: null,
      },
    });
    renderWithProviders(<HousePage />);

    const heading = await screen.findByRole("heading", { name: "Set aside" });
    const section = heading.closest("section") as HTMLElement;
    expect(
      within(section).getAllByTitle("Enter the bank balance in House settings"),
    ).toHaveLength(2);
  });

  it("lists each owner's deposits under the buckets", async () => {
    serveHouse(makeHouseResponse());
    renderWithProviders(<HousePage />);

    const table = await screen.findByRole("table", { name: "Deposits" });
    const [, alice, bob] = within(table).getAllByRole("row");
    expect(alice).toHaveTextContent("Alice$4,000.00$0.00$1,825.00$2,175.00");
    expect(bob).toHaveTextContent("Bob$2,200.00$1,000.00$1,785.00$1,415.00");
  });

  it("says so when a list is empty", async () => {
    serveHouse(
      makeHouseResponse({
        loans: [],
        upcoming: [],
        set_aside: {
          buckets: [],
          total: 0,
          bank_balance: null,
          bank_balance_as_of: null,
          difference: null,
          owners: [],
        },
        recent_activity: [],
      }),
    );
    renderWithProviders(<HousePage />);

    expect(
      await screen.findByText("No loans recorded yet."),
    ).toBeInTheDocument();
    expect(screen.getByText("Nothing coming due.")).toBeInTheDocument();
    expect(screen.getByText("No money set aside yet.")).toBeInTheDocument();
    expect(screen.getByText("No activity yet.")).toBeInTheDocument();
  });

  it("points to Settings when no house is set up", async () => {
    serveHouse(makeHouseResponse({ asset: null }));
    renderWithProviders(<HousePage />);

    const banner = (await screen.findByText("No house set up yet")).closest(
      "[role=status]",
    ) as HTMLElement;
    expect(
      within(banner).getByRole("link", { name: "Set up the home in Settings" }),
    ).toHaveAttribute("href", "/settings#settings-house");
  });

  it("shows the asset name and no Example pills on real Put in and Shares", async () => {
    serveHouse(withExamples(["loans", "upcoming"]));
    renderWithProviders(<HousePage />);

    expect(await screen.findByText("Maple Street")).toBeInTheDocument();
    expect(screen.queryByText("No house set up yet")).not.toBeInTheDocument();
    const pills = screen.getAllByText("Example");
    expect(pills).toHaveLength(2);
    for (const id of ["house-put-in", "house-shares"]) {
      const section = document.querySelector(
        `section[aria-labelledby="${id}"]`,
      ) as HTMLElement;
      expect(within(section).queryByText("Example")).not.toBeInTheDocument();
    }
  });

  it("records a credit with the entered split", async () => {
    serveHouse(withExamples([]));
    let body: unknown;
    server.use(
      http.post("/api/v1/house/manual-entries", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<HousePage />);

    await user.click(
      await screen.findByRole("button", { name: "Record a credit" }),
    );
    const dialog = await screen.findByRole("dialog");
    const date = within(dialog).getByLabelText("Date");
    await user.clear(date);
    await user.type(date, "2026-10-01");
    await user.type(within(dialog).getByLabelText("Amount"), "1200");
    await user.selectOptions(
      within(dialog).getByLabelText("Kind"),
      "insurance",
    );
    await user.type(
      within(dialog).getByLabelText("Description"),
      "First premium",
    );
    await user.type(
      within(dialog).getByLabelText("Document reference"),
      "PL-7",
    );
    const alice = within(dialog).getByLabelText(/Alice/);
    await user.clear(alice);
    await user.type(alice, "70");
    await user.click(
      within(dialog).getByRole("button", { name: "Record a credit" }),
    );

    await waitFor(() =>
      expect(body).toEqual({
        account_name: "Escrow",
        date: "2026-10-01",
        amount: 1200,
        description: "First premium",
        document_ref: "PL-7",
        share_kind: "insurance",
        owner_shares: { [ALICE_ID]: 70, [BOB_ID]: 30 },
      }),
    );
  });

  it("sends nothing when the credit dialog is cancelled", async () => {
    serveHouse(withExamples([]));
    let posted = false;
    server.use(
      http.post("/api/v1/house/manual-entries", () => {
        posted = true;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<HousePage />);
    await user.click(
      await screen.findByRole("button", { name: "Record a credit" }),
    );
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(posted).toBe(false);
  });

  it("shows the server message when a credit is refused", async () => {
    serveHouse(withExamples([]));
    server.use(
      http.post("/api/v1/house/manual-entries", () =>
        HttpResponse.json(
          { error: { code: "FINALIZED", message: "Month is finalized" } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<HousePage />);
    await user.click(
      await screen.findByRole("button", { name: "Record a credit" }),
    );
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Amount"), "5");
    await user.type(within(dialog).getByLabelText("Description"), "x");
    await user.click(
      within(dialog).getByRole("button", { name: "Record a credit" }),
    );
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Month is finalized",
    );
  });

  it("lists recorded credits and deletes one after confirming", async () => {
    serveHouse(withExamples([]));
    let deleted: string | undefined;
    server.use(
      http.get("/api/v1/house/manual-entries", () =>
        HttpResponse.json([
          {
            id: "m1",
            account_name: "Escrow",
            date: "2026-09-30",
            amount: 8000,
            description: "Closing costs",
            document_ref: "CD-1",
            share_kind: "closing",
            owner_shares: { [ALICE_ID]: 100, [BOB_ID]: 0 },
          },
        ]),
      ),
      http.delete("/api/v1/house/manual-entries/:id", ({ params }) => {
        deleted = params.id as string;
        return HttpResponse.json({ deleted: true });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<HousePage />);

    expect(await screen.findByText("Closing costs")).toBeInTheDocument();
    expect(screen.getByText(/Alice 100%, Bob 0%/)).toHaveTextContent("CD-1");
    expect(screen.getByText("$8,000.00")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Delete Closing costs" }),
    );
    const dialog = await screen.findByRole("dialog");
    await user.click(
      within(dialog).getByRole("button", { name: "Delete credit" }),
    );
    await waitFor(() => expect(deleted).toBe("m1"));
  });

  it("says so when no credits are recorded", async () => {
    serveHouse(withExamples([]));
    renderWithProviders(<HousePage />);
    expect(
      await screen.findByText("No credits recorded by hand yet."),
    ).toBeInTheDocument();
  });
});
