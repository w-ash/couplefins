import { Pill } from "@/components/Pill";

interface SectionHeaderProps {
  title: string;
  description?: string;
  id?: string;
  /** Marks the section as showing example figures. */
  example?: boolean;
}

export function SectionHeader({
  title,
  description,
  id,
  example = false,
}: SectionHeaderProps) {
  const heading = (
    <h2
      id={id}
      className={`font-medium text-lg text-foreground ${example ? "" : "mb-1"}`}
    >
      {title}
    </h2>
  );
  return (
    <>
      {example ? (
        <div className="mb-1 flex items-center gap-2">
          {heading}
          <Pill title="Example figures — not yet from the real ledger">
            Example
          </Pill>
        </div>
      ) : (
        heading
      )}
      {description && (
        <p className="mb-4 text-xs text-muted-foreground">{description}</p>
      )}
    </>
  );
}
