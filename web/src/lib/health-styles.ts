export interface HealthStyle {
  color: string;
  barColor: string;
  label: string;
  iconColor: string;
}

const HEALTH_STYLES: Record<string, HealthStyle> = {
  on_track: {
    color: "text-positive",
    barColor: "bg-primary",
    label: "On track",
    iconColor: "text-positive",
  },
  near_limit: {
    color: "text-warning-muted-foreground",
    barColor: "bg-warning",
    label: "Near limit",
    iconColor: "text-warning",
  },
  over_budget: {
    color: "text-destructive-muted-foreground",
    barColor: "bg-destructive",
    label: "Over budget",
    iconColor: "text-destructive",
  },
};

const DEFAULT_HEALTH: HealthStyle = {
  color: "text-muted-foreground",
  barColor: "bg-muted",
  label: "",
  iconColor: "",
};

export function getHealthStyle(health: string | null): HealthStyle {
  return health ? (HEALTH_STYLES[health] ?? DEFAULT_HEALTH) : DEFAULT_HEALTH;
}
