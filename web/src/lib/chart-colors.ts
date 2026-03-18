/**
 * Deterministic chart color palette for category group sparklines.
 * Colors are defined as CSS custom properties in app.css with
 * light/dark variants tuned for WCAG AA contrast on each background.
 */
const CHART_COLORS = Array.from({ length: 12 }, (_, i) => `var(--chart-${i})`);

export function getChartColor(index: number): string {
  return CHART_COLORS[index % CHART_COLORS.length];
}
