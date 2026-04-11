const VOICES = [
  {
    value: "fiona",
    label: "Fiona",
    description: "Warm, direct, uses plain language. A CPA from Louisiana.",
  },
  {
    value: "standard",
    label: "Standard",
    description: "Neutral, minimal personality. Just the facts.",
  },
] as const;

export function ChatVoiceSelector({
  currentVoice,
  onPersist,
}: {
  currentVoice: string;
  onPersist: (voice: string) => void;
}) {
  return (
    <fieldset className="space-y-3" aria-label="Chat personality">
      {VOICES.map(({ value, label, description }) => (
        <label
          key={value}
          className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
            currentVoice === value
              ? "border-primary bg-primary/5"
              : "border-border hover:border-muted-foreground/30"
          }`}
        >
          <input
            type="radio"
            name="chat-voice"
            value={value}
            checked={currentVoice === value}
            onChange={() => onPersist(value)}
            className="mt-0.5 accent-primary"
          />
          <div>
            <span className="text-sm font-medium text-foreground">{label}</span>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </label>
      ))}
    </fieldset>
  );
}
