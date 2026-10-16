import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { HouseResponse } from "@/api/generated/model";
import { useIdentityStore } from "@/lib/identity";
import { ALICE_ID, makeHouseResponse } from "@/test/house-fixtures";
import { server } from "@/test/server";
import { renderWithProviders, screen } from "@/test/test-utils";
import { HousePage } from "./HousePage";

function serveHouse(response: HouseResponse) {
  server.use(http.get("/api/v1/house", () => HttpResponse.json(response)));
}

describe("HousePage", () => {
  beforeEach(() => {
    useIdentityStore.setState({ currentPersonId: ALICE_ID });
  });

  it("shows the example notice only for example data", async () => {
    serveHouse(makeHouseResponse({ is_example: true }));
    const { unmount } = renderWithProviders(<HousePage />);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Example figures",
    );
    unmount();

    serveHouse(makeHouseResponse({ is_example: false }));
    renderWithProviders(<HousePage />);
    await screen.findByRole("heading", { name: "Put in" });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
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

  it("says so when a list is empty", async () => {
    serveHouse(
      makeHouseResponse({
        loans: [],
        upcoming: [],
        set_aside: { buckets: [], total: 0 },
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
});
