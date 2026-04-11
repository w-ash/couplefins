import { Button } from "@/components/Button";

const DEFAULT_SUGGESTIONS = [
  "Who owes whom?",
  "Are we on budget?",
  "What did we spend on groceries this month?",
  "What's our upload status?",
];

export function SuggestedQuestions({
  onSelect,
}: {
  onSelect: (question: string) => void;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-4">
      <p className="text-sm text-muted-foreground">
        Ask about spending, budgets, or settlements
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        {DEFAULT_SUGGESTIONS.map((q) => (
          <Button
            key={q}
            variant="secondary"
            size="sm"
            className="rounded-full"
            onClick={() => onSelect(q)}
          >
            {q}
          </Button>
        ))}
      </div>
    </div>
  );
}
