/**
 * Deterministic chart color palette for category group sparklines.
 * 12 OKLCH colors spread across the hue wheel, tuned for warm theme.
 * Each color works on both light and dark backgrounds at WCAG AA.
 */
const CHART_COLORS = [
  "oklch(0.55 0.12 175)", // teal
  "oklch(0.58 0.14 27)", // coral
  "oklch(0.55 0.11 265)", // indigo
  "oklch(0.62 0.13 55)", // amber
  "oklch(0.52 0.12 145)", // green
  "oklch(0.56 0.13 325)", // plum
  "oklch(0.58 0.12 205)", // cyan
  "oklch(0.55 0.14 15)", // red-orange
  "oklch(0.54 0.10 235)", // blue
  "oklch(0.60 0.12 85)", // gold
  "oklch(0.53 0.11 295)", // violet
  "oklch(0.57 0.11 115)", // lime
] as const;

export function getChartColor(index: number): string {
  return CHART_COLORS[index % CHART_COLORS.length];
}
