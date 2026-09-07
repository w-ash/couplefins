import type { ComponentProps } from "react";
import { describe, expect, it } from "vitest";
import { buildSankeyData } from "@/lib/spending-flow";
import { cell, makeFlowContext } from "@/test/insights-fixtures";
import { renderWithProviders, screen } from "@/test/test-utils";
import { FlowTooltip } from "./SpendingFlowChart";

const ctx = makeFlowContext();
const dataset = buildSankeyData(
  [
    cell({ category: "Dining Out", amount: 300, transaction_count: 3 }),
    cell({ category: "Groceries", amount: 100, transaction_count: 1 }),
  ],
  ctx,
);
const total = 400;

type FlowDatum = NonNullable<
  NonNullable<ComponentProps<typeof FlowTooltip>["payload"]>[number]["payload"]
>["payload"];

/** Recharts hands the tooltip `{ payload: { payload, name, value } }`. */
function rechartsPayload(item: FlowDatum, name: string, value: number) {
  return [{ payload: { payload: item, name, value } }];
}

describe("FlowTooltip", () => {
  it("reads the node through the recharts wrapper", () => {
    const node = dataset.nodes.find((n) => n.name === "Dining Out");
    if (!node) throw new Error("no category node");
    renderWithProviders(
      <FlowTooltip
        active
        payload={rechartsPayload(node, node.name, node.amount)}
        total={total}
      />,
    );
    expect(screen.getByText("Dining Out")).toBeInTheDocument();
    expect(screen.getByText("$300.00")).toBeInTheDocument();
    expect(
      screen.getByText(/75% of the period · 3 transactions/),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("NaN");
  });

  it("shows source → target for a link", () => {
    const [source, target] = dataset.nodes;
    if (!source || !target) throw new Error("no nodes");
    renderWithProviders(
      <FlowTooltip
        active
        payload={rechartsPayload(
          { source, target, value: 100 },
          `${source.name} - ${target.name}`,
          100,
        )}
        total={total}
      />,
    );
    expect(
      screen.getByText(`${source.name} → ${target.name}`),
    ).toBeInTheDocument();
    expect(screen.getByText("$100.00")).toBeInTheDocument();
  });

  it("renders nothing when inactive or empty", () => {
    const { container } = renderWithProviders(
      <FlowTooltip payload={[]} total={total} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
