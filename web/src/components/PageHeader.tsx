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
    <div className="mb-8 flex items-center justify-between">
      <h1 className="flex items-center gap-2.5 font-semibold text-2xl text-foreground">
        {icon}
        {title}
        {badge}
      </h1>
      {children}
    </div>
  );
}
