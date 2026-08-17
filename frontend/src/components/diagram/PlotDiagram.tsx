import { useMemo } from 'react'
import { motion } from 'motion/react'
import type { PlotDiagram as PlotSpec } from '../../api'
import { axisLabel, makeScale, resolveYRange, sampleSeries, VIEW } from './layout'
import { toneStroke } from './tones'
import type { StepState } from './useDiagramSteps'
import { springDefault } from '../../motion/springs'

interface Props {
  spec: PlotSpec
  steps: StepState
}

const MARGIN = 16

/**
 * Curves, scatter and bars on labelled axes.
 *
 * Curves are sampled from a fixed menu of families in layout.ts — there is no
 * expression string anywhere in this path, so nothing the model wrote is ever
 * evaluated. A "function" series is 97 sampled points and a polyline.
 */
export default function PlotDiagram({ spec, steps }: Props) {
  const sampled = useMemo(
    () => spec.series.map((s) => sampleSeries(s, spec.x_range)),
    [spec],
  )
  const yRange = useMemo(() => resolveYRange(spec.y_range, sampled), [spec, sampled])
  const scale = useMemo(() => makeScale(spec.x_range, yRange, MARGIN), [spec, yRange])

  const gated = steps.visible.size > 0
  const shows = (id: string) => !gated || steps.visible.has(id)
  const emphasises = (id: string) => steps.active.has(id)

  const axisY = clampToPlot(scale({ x: spec.x_range[0], y: 0 }).y)
  const axisX = clampToPlot(scale({ x: 0, y: yRange[0] }).x)

  return (
    <>
      {/* Frame first: everything else reads against it. */}
      <rect
        x={MARGIN}
        y={MARGIN}
        width={VIEW - MARGIN * 2}
        height={VIEW - MARGIN * 2}
        fill="var(--color-surface)"
        stroke="var(--color-hairline)"
        strokeWidth={0.5}
      />

      {/* Zero lines only when zero is actually in range — an axis drawn at the
          edge of the plot claims the origin is there when it is not. */}
      {yRange[0] < 0 && yRange[1] > 0 && (
        <line
          x1={MARGIN}
          y1={axisY}
          x2={VIEW - MARGIN}
          y2={axisY}
          stroke="var(--color-border)"
          strokeWidth={0.5}
        />
      )}
      {spec.x_range[0] < 0 && spec.x_range[1] > 0 && (
        <line
          x1={axisX}
          y1={MARGIN}
          x2={axisX}
          y2={VIEW - MARGIN}
          stroke="var(--color-border)"
          strokeWidth={0.5}
        />
      )}

      {spec.series.map((series, i) => {
        if (!shows(series.id)) return null
        const points = sampled[i]
        if (points.length === 0) return null

        const active = emphasises(series.id)
        const stroke = toneStroke(series.tone)
        const width = active ? 1.6 : 1.1

        if (series.type === 'points') {
          return (
            <g key={series.id}>
              {points.map((p, j) => {
                const at = scale(p)
                return <circle key={j} cx={at.x} cy={at.y} r={active ? 1.4 : 1} fill={stroke} />
              })}
            </g>
          )
        }

        if (series.type === 'bars') {
          const barWidth = Math.max((VIEW - MARGIN * 2) / (points.length * 1.6), 1.2)
          return (
            <g key={series.id}>
              {points.map((p, j) => {
                const top = scale(p)
                const base = scale({ x: p.x, y: Math.max(yRange[0], 0) })
                return (
                  <motion.rect
                    key={j}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: active ? 1 : 0.85 }}
                    transition={springDefault}
                    x={top.x - barWidth / 2}
                    y={Math.min(top.y, base.y)}
                    width={barWidth}
                    height={Math.abs(base.y - top.y)}
                    fill={stroke}
                    rx={0.4}
                  />
                )
              })}
            </g>
          )
        }

        return (
          <motion.polyline
            key={series.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={springDefault}
            points={points.map((p) => { const at = scale(p); return `${at.x},${at.y}` }).join(' ')}
            fill="none"
            stroke={stroke}
            strokeWidth={width}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        )
      })}

      {spec.markers.map((marker) => {
        if (!shows(marker.id)) return null
        const at = scale({ x: marker.at[0], y: marker.at[1] })
        const active = emphasises(marker.id)
        return (
          <g key={marker.id}>
            <circle
              cx={at.x}
              cy={at.y}
              r={active ? 2 : 1.5}
              fill="var(--color-brand-500)"
              stroke="var(--color-surface)"
              strokeWidth={0.6}
            />
            <text
              x={at.x}
              y={at.y - 3}
              textAnchor="middle"
              fontSize={3.2}
              fill="var(--color-fg-muted)"
              fontFamily="var(--font-sans)"
            >
              {marker.label}
            </text>
          </g>
        )
      })}

      <g fill="var(--color-fg-faint)" fontSize={3} fontFamily="var(--font-sans)">
        <text x={MARGIN} y={VIEW - MARGIN + 4.5}>{axisLabel(spec.x_range[0])}</text>
        <text x={VIEW - MARGIN} y={VIEW - MARGIN + 4.5} textAnchor="end">
          {axisLabel(spec.x_range[1])}
        </text>
        <text x={MARGIN - 1.5} y={VIEW - MARGIN} textAnchor="end">{axisLabel(yRange[0])}</text>
        <text x={MARGIN - 1.5} y={MARGIN + 2} textAnchor="end">{axisLabel(yRange[1])}</text>
      </g>

      <g fill="var(--color-fg-subtle)" fontSize={3.4} fontFamily="var(--font-sans)">
        <text x={VIEW / 2} y={VIEW - 2} textAnchor="middle">{spec.x_label}</text>
        <text
          x={4}
          y={VIEW / 2}
          textAnchor="middle"
          transform={`rotate(-90 4 ${VIEW / 2})`}
        >
          {spec.y_label}
        </text>
      </g>

      {spec.series.length > 1 && (
        <g fontSize={3} fontFamily="var(--font-sans)">
          {spec.series.map((series, i) => (
            <g key={series.id} transform={`translate(${MARGIN + 2}, ${MARGIN + 3 + i * 4.5})`}>
              <rect width={3} height={1.2} y={-1} rx={0.4} fill={toneStroke(series.tone)} />
              <text x={4.5} y={0.6} fill="var(--color-fg-muted)">{series.label}</text>
            </g>
          ))}
        </g>
      )}
    </>
  )
}

/** Keep a computed axis position inside the plot frame. */
function clampToPlot(value: number): number {
  return Math.min(Math.max(value, MARGIN), VIEW - MARGIN)
}
