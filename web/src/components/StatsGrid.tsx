interface Stat {
  label: string;
  value: string;
  description?: string;
  valueClassName?: string;
}

export function StatsGrid({ stats }: { stats: Stat[] }) {
  return (
    <div
      className={`grid gap-3 ${stats.length <= 3 ? "grid-cols-1 sm:grid-cols-3" : "grid-cols-2 sm:grid-cols-4"}`}
    >
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="flex flex-col justify-between rounded-lg border border-border bg-card p-4 shadow-sm"
        >
          <p className="text-xs font-medium text-muted-foreground">
            {stat.label}
          </p>
          <p
            className={`mt-1 text-lg font-semibold tabular-nums text-right ${stat.valueClassName ?? "text-foreground"}`}
          >
            {stat.value}
          </p>
          {stat.description && (
            <p className="mt-1 text-[11px] leading-tight text-muted-foreground/70">
              {stat.description}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
