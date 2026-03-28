import { ArrowRight, Tag } from "lucide-react";
import { useState } from "react";
import { Card } from "@/components/Card";
import { ExpandChevron } from "@/components/ExpandChevron";
import { ClassificationBadge } from "@/lib/transaction-classification";

const TAG_EXAMPLES = [
  {
    tag: "shared",
    type: "shared" as const,
    description: "Split 50/50 between you",
  },
  {
    tag: "s70",
    type: "shared" as const,
    description: "You pay 70%, partner owes the rest",
  },
  {
    tag: "household",
    type: "household" as const,
    description: "Counts toward budget, no split",
  },
  {
    tag: "bob",
    type: "spotted" as const,
    otherPersonName: "Bob",
    description: "You fronted it — Bob pays you back",
  },
  {
    tag: null,
    type: "personal" as const,
    description: "Not shared, not tracked",
  },
] as const;

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
        How tags work
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-border-muted px-5 pb-5">
          <p className="pt-3 text-sm text-muted-foreground">
            Tag transactions in Monarch before exporting. Tags control how
            expenses are classified and split.
          </p>

          {TAG_EXAMPLES.map((example) => (
            <div
              key={example.tag ?? "none"}
              className="flex flex-wrap items-center gap-2"
            >
              {example.tag ? (
                <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">
                  {example.tag}
                </code>
              ) : (
                <span className="text-xs italic text-muted-foreground/70">
                  no tag
                </span>
              )}
              <ArrowRight className="size-3 text-muted-foreground" />
              <ClassificationBadge
                type={example.type}
                otherPersonName={
                  "otherPersonName" in example
                    ? example.otherPersonName
                    : undefined
                }
              />
              <span className="text-sm text-muted-foreground">
                {example.description}
              </span>
            </div>
          ))}

          <p className="pt-1 text-xs text-muted-foreground">
            Combine tags for custom splits —{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
              shared, s70
            </code>{" "}
            for a 70/30 split.
          </p>
        </div>
      )}
    </Card>
  );
}
