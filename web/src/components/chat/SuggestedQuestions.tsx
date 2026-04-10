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
          <button
            key={q}
            type="button"
            onClick={() => onSelect(q)}
            className="rounded-full border border-border px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-muted"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
