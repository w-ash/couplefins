export function PageHeader({
  icon,
  title,
  badge,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  badge?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:mb-8 sm:flex-row sm:items-center sm:justify-between">
      <h1 className="flex items-center gap-2.5 font-semibold text-2xl text-foreground">
        {icon}
        {title}
        {badge}
      </h1>
      {children}
    </div>
  );
}
