type BadgeSize = "xs" | "sm" | "base" | "lg";

const sizeStyles: Record<BadgeSize, string> = {
  xs: "px-2 py-0.5 text-xs font-medium",
  sm: "px-2.5 py-0.5 text-sm font-medium",
  base: "px-2.5 py-0.5 text-base font-semibold",
  lg: "px-2.5 py-0.5 text-lg font-semibold",
};

export function PersonBadge({
  name,
  accentColor,
  size = "sm",
}: {
  name: string;
  accentColor: string;
  size?: BadgeSize;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full ${sizeStyles[size]} ${accentColor}`}
    >
      {name}
    </span>
  );
}
