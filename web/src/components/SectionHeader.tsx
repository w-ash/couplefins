interface SectionHeaderProps {
  title: string;
  description?: string;
  id?: string;
}

export function SectionHeader({ title, description, id }: SectionHeaderProps) {
  return (
    <>
      <h2 id={id} className="mb-1 font-medium text-lg text-foreground">
        {title}
      </h2>
      {description && (
        <p className="mb-4 text-xs text-muted-foreground">{description}</p>
      )}
    </>
  );
}
