interface Stat {
  label: string;
  value: string;
  valueClassName?: string;
}

export function StatsGrid({ stats }: { stats: Stat[] }) {
  return (
    <div className="grid grid-cols-3 gap-3">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="rounded-lg border border-border bg-card p-4 shadow-sm"
        >
          <p className="text-xs font-medium text-muted-foreground">
            {stat.label}
          </p>
          <p
            className={`mt-1 text-lg font-semibold tabular-nums text-right ${stat.valueClassName ?? "text-foreground"}`}
          >
            {stat.value}
          </p>
        </div>
      ))}
    </div>
  );
}
