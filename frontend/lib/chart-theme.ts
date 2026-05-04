/**
 * GRIDMIND Recharts theme.
 *
 * Centralised palette and reusable props so every chart looks coherent.
 * Existing charts can opt in incrementally — pass these into <CartesianGrid />,
 * <XAxis />, <YAxis />, <Tooltip />, etc.
 */

export const chartPalette = {
  /** Primary series — lime accent. */
  primary: "#B5F23A",
  /** Secondary series — magenta highlight. */
  secondary: "#FF3D8A",
  /** Tertiary — muted slate-green for low-emphasis lines. */
  tertiary: "#5C6F66",
  /** Quaternary — bright teal for "actual vs forecast" deltas. */
  quaternary: "#14B89A",
  /** Used for forecast / projected series. */
  forecast: "#D4F77C",
  /** Status colors. */
  ok: "#14B89A",
  warn: "#F59E0B",
  danger: "#EF4444",
} as const;

export const seriesPalette: string[] = [
  chartPalette.primary,
  chartPalette.secondary,
  chartPalette.quaternary,
  chartPalette.tertiary,
  chartPalette.forecast,
];

/** Pick a colour for series index `i`, wrapping. */
export function seriesColor(i: number): string {
  return seriesPalette[i % seriesPalette.length] as string;
}

/** Default props for <CartesianGrid />. */
export const gridProps = {
  stroke: "rgba(92, 111, 102, 0.18)",
  strokeDasharray: "2 4",
  vertical: false,
} as const;

/** Default props for <XAxis /> / <YAxis />. */
export const axisProps = {
  stroke: "rgba(92, 111, 102, 0.55)",
  tick: { fill: "rgba(92, 111, 102, 0.85)", fontSize: 11 },
  tickLine: false,
  axisLine: false,
} as const;

/** Default contentStyle for <Tooltip />. */
export const tooltipStyle = {
  background: "rgba(13, 22, 20, 0.95)",
  border: "1px solid rgba(181, 242, 58, 0.25)",
  borderRadius: 12,
  padding: "8px 12px",
  fontSize: 12,
  color: "#F4F7F1",
  boxShadow: "0 8px 24px -12px rgba(0, 0, 0, 0.45)",
} as const;

/** Default itemStyle for <Tooltip />. */
export const tooltipItemStyle = {
  color: "#F4F7F1",
  padding: "1px 0",
} as const;

/** Default labelStyle for <Tooltip />. */
export const tooltipLabelStyle = {
  color: "rgba(244, 247, 241, 0.55)",
  fontSize: 10,
  textTransform: "uppercase" as const,
  letterSpacing: "0.08em",
  marginBottom: 4,
} as const;

/** All-in-one default props bundle for a Recharts <Tooltip />. */
export const tooltipProps = {
  contentStyle: tooltipStyle,
  itemStyle: tooltipItemStyle,
  labelStyle: tooltipLabelStyle,
  cursor: { stroke: "rgba(181, 242, 58, 0.35)", strokeWidth: 1 },
} as const;

/** Defaults for <Legend />. */
export const legendProps = {
  iconType: "circle" as const,
  iconSize: 8,
  wrapperStyle: { fontSize: 11, color: "rgba(92, 111, 102, 0.85)" },
} as const;
