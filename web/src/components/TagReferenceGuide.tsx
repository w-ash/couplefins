import { Tag } from "lucide-react";
import { useState } from "react";
import { Card } from "@/components/Card";
import { ExpandChevron } from "@/components/ExpandChevron";

const ROWS = [
  {
    tag: "shared or split",
    what: "Split 50/50",
    detail: "Both people share the cost equally",
  },
  {
    tag: "shared, s70",
    what: "Custom split",
    detail: "You pay 70%, your partner pays 30%",
  },
  {
    tag: "household",
    what: "Budget only",
    detail: "Counts toward your household budget, but no money changes hands",
  },
  {
    tag: "bob",
    what: "Spotted",
    detail: "You fronted the money — your partner pays you back in full",
  },
  {
    tag: "settlement",
    what: "Settlement payment",
    detail:
      "Transfers to your partner — excluded from spending totals. You can also link them from Settle Up.",
  },
  {
    tag: null,
    what: "Personal",
    detail: "Your own expense, not in the household budget",
  },
] as const;

const LABELS = [
  {
    tag: "line:mortgage",
    what: "Budget line",
    detail: "The budget line of a joint-account row, e.g. line:mortgage",
  },
  {
    tag: "pot:renovation",
    what: "Pot",
    detail:
      "The bucket a joint deposit, payment, or pot-to-pot transfer belongs to",
  },
  {
    tag: "source:own or source:gift",
    what: "Funding source",
    detail:
      "Whose money a joint deposit is: the depositor's own, or a gift to them. Own when absent.",
  },
  {
    tag: "share:<kind>",
    what: "Contribution kind",
    detail: "Reserved for v1.15.4: a qualifying contribution kind",
  },
  {
    tag: "loan:<slug>",
    what: "Loan",
    detail: "Reserved for v1.15.5: the loan a payment pays",
  },
] as const;

type GuideRow = {
  tag: string | null;
  what: string;
  detail: string;
};

function GuideTable({
  rows,
  tagHeading,
}: {
  rows: readonly GuideRow[];
  tagHeading: string;
}) {
  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b border-border-muted text-xs text-muted-foreground">
          <th className="pb-2 pr-4 font-medium">{tagHeading}</th>
          <th className="pb-2 pr-4 font-medium">What happens</th>
          <th className="hidden pb-2 font-medium sm:table-cell">Example</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-border-muted">
        {rows.map((row) => (
          <tr key={row.tag ?? "none"}>
            <td className="py-2.5 pr-4 align-top">
              {row.tag ? (
                <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">
                  {row.tag}
                </code>
              ) : (
                <span className="text-xs italic text-muted-foreground/70">
                  no tag
                </span>
              )}
            </td>
            <td className="py-2.5 pr-4 align-top font-medium text-foreground">
              {row.what}
            </td>
            <td className="hidden py-2.5 align-top text-muted-foreground sm:table-cell">
              {row.detail}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function TagReferenceGuide() {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="mt-6 p-0">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className="flex w-full items-center gap-2 px-5 py-4 text-left text-sm font-medium text-foreground transition-colors hover:bg-muted/50"
      >
        <ExpandChevron expanded={expanded} />
        <Tag className="size-4 text-muted-foreground" />
        How Monarch tags work
      </button>

      {expanded && (
        <div className="border-t border-border-muted px-5 pb-5">
          <p className="py-3 text-sm text-muted-foreground">
            Tag transactions in Monarch before exporting. The tag determines how
            each expense is classified and split.
          </p>

          <GuideTable rows={ROWS} tagHeading="Tag in Monarch" />

          <h3 className="mt-6 text-sm font-medium text-foreground">Labels</h3>
          <p className="py-2 text-sm text-muted-foreground">
            A tag written <code className="font-mono text-xs">name:value</code>{" "}
            is a label for the joint-account pages. Values may contain letters,
            digits, spaces, <code className="font-mono text-xs">.</code>,{" "}
            <code className="font-mono text-xs">_</code>, and{" "}
            <code className="font-mono text-xs">-</code>. Labels never change a
            split. An import never removes a label, whether it came from Monarch
            or the app: remove or rename a label in the app's tag editor. Pot
            balances are computed from these tags.
          </p>
          <GuideTable rows={LABELS} tagHeading="Label" />
        </div>
      )}
    </Card>
  );
}
