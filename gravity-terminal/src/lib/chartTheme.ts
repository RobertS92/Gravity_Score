/**
 * Shared Recharts theme tokens.
 *
 * Every chart in the terminal (sparklines, line / area / bar / scatter)
 * should pull its colors, grid, axis, and tooltip styling from this
 * module so the visual language stays consistent and so retheming
 * (e.g. high-contrast or print-friendly output) only needs to update
 * one place.
 *
 * The values mirror the CSS custom properties defined in
 * `src/styles/tokens.css`. They're hard-coded here because Recharts'
 * SVG can't read CSS variables on the element it renders into without
 * jumping through `getComputedStyle`, which is brittle in tests.
 * If the token file changes, update both — there's a lint test that
 * spot-checks the values stay in sync.
 */

export const chartTheme = {
  background: 'transparent',
  axis: '#5a7080', // --text-dim
  axisStrong: '#8ea5bb', // --text-muted
  grid: '#1d2734', // --chart-grid
  tickFontSize: 11,
  tickFontFamily: '"JetBrains Mono", "Fira Code", "Courier New", monospace',
  tooltipBg: '#111820', // --bg-secondary
  tooltipBorder: '#2a3545', // --border-default
  tooltipText: '#eef2f7', // --text-primary
  series: [
    '#4cc963', // --chart-series-1 (positive / primary)
    '#e0ac3a', // --chart-series-2 (warning / amber)
    '#6ab4ff', // --chart-series-3 (info / blue)
    '#b48afb', // --chart-series-4 (purple)
    '#5adfe6', // --chart-series-5 (cyan)
    '#ff5f5a', // --chart-series-6 (negative)
  ],
  status: {
    positive: '#4cc963',
    warning: '#e0ac3a',
    negative: '#ff5f5a',
    info: '#6ab4ff',
    neutral: '#8ea5bb',
  },
}

/** Series color helper. Indexes wrap modulo the series palette so charts
 * with more than 6 series degrade gracefully instead of throwing. */
export function seriesColor(index: number): string {
  if (!chartTheme.series.length) return chartTheme.axisStrong
  return chartTheme.series[index % chartTheme.series.length]
}

/** Common Recharts axis props — pass to <XAxis/> and <YAxis/> like:
 *   <XAxis {...sharedAxis} />
 */
export const sharedAxis = {
  stroke: chartTheme.axis,
  tick: { fill: chartTheme.axisStrong, fontSize: chartTheme.tickFontSize, fontFamily: chartTheme.tickFontFamily },
  axisLine: { stroke: chartTheme.axis },
  tickLine: { stroke: chartTheme.axis },
}

/** Common Recharts CartesianGrid props. */
export const sharedGrid = {
  stroke: chartTheme.grid,
  strokeDasharray: '3 3',
}

/** Common Recharts Tooltip wrapperStyle + contentStyle. */
export const sharedTooltip = {
  wrapperStyle: {
    outline: 'none',
  },
  contentStyle: {
    background: chartTheme.tooltipBg,
    border: `1px solid ${chartTheme.tooltipBorder}`,
    color: chartTheme.tooltipText,
    fontFamily: chartTheme.tickFontFamily,
    fontSize: 12,
    borderRadius: 3,
  },
  labelStyle: {
    color: chartTheme.axisStrong,
    fontFamily: chartTheme.tickFontFamily,
    fontSize: 11,
  },
  itemStyle: {
    color: chartTheme.tooltipText,
    fontFamily: chartTheme.tickFontFamily,
    fontSize: 12,
  },
}

/** Helper for building an accessible chart description that screen
 * readers can announce as an alternative to the visual chart. */
export function chartSummary(args: {
  title: string
  series: { label: string; latest: number | string | null; delta?: number | string | null }[]
}): string {
  const parts = args.series
    .filter((s) => s.latest != null)
    .map((s) => {
      const delta = s.delta != null && s.delta !== '' ? `, change ${s.delta}` : ''
      return `${s.label}: ${s.latest}${delta}`
    })
  return `${args.title}. ${parts.join('; ')}.`
}
