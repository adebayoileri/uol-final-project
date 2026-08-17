import { useMemo } from 'react'
import { motion } from 'motion/react'
import type { GeometryDiagram as GeometrySpec } from '../../api'
import {
  fitPoints,
  interiorAngles,
  rectangleFromSides,
  regularPolygon,
  triangleFromSides,
  VIEW,
  type Point,
} from './layout'
import type { StepState } from './useDiagramSteps'
import { springDefault } from '../../motion/springs'

interface Props {
  spec: GeometrySpec
  steps: StepState
}

/**
 * Shapes drawn from side lengths.
 *
 * The model supplies `sides: [3, 4, 5]` and never a coordinate, so "can this
 * shape exist" was settled by the backend's triangle-inequality check before
 * anything reached here. That is why triangleFromSides can clamp its acos
 * domain and still be sure the answer is meaningful.
 */
export default function GeometryDiagram({ spec, steps }: Props) {
  const points = useMemo(() => fitPoints(rawPoints(spec)), [spec])
  const angles = useMemo(
    () => (spec.shape === 'circle' ? [] : interiorAngles(points)),
    [points, spec.shape],
  )

  const gated = steps.visible.size > 0
  const shows = (id: string) => !gated || steps.visible.has(id)
  const emphasises = (id: string) => steps.active.has(id)

  if (spec.shape === 'circle') {
    const r = VIEW * 0.34
    return (
      <>
        <circle
          cx={VIEW / 2}
          cy={VIEW / 2}
          r={r}
          fill="var(--color-brand-500)"
          fillOpacity={0.1}
          stroke="var(--color-brand-500)"
          strokeWidth={1.1}
        />
        {spec.show_sides && (
          <>
            <line
              x1={VIEW / 2}
              y1={VIEW / 2}
              x2={VIEW / 2 + r}
              y2={VIEW / 2}
              stroke="var(--color-fg-muted)"
              strokeWidth={0.7}
              strokeDasharray="2 1.5"
            />
            <text
              x={VIEW / 2 + r / 2}
              y={VIEW / 2 - 2}
              textAnchor="middle"
              fontSize={3.4}
              fill="var(--color-fg-muted)"
              fontFamily="var(--font-sans)"
            >
              r = {spec.radius}
            </text>
          </>
        )}
        <circle cx={VIEW / 2} cy={VIEW / 2} r={1} fill="var(--color-fg-muted)" />
        <Annotations spec={spec} points={[]} centre={{ x: VIEW / 2, y: VIEW / 2 }} />
      </>
    )
  }

  const path = points.map((p) => `${p.x},${p.y}`).join(' ')
  const centre = centroid(points)

  return (
    <>
      <motion.polygon
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={springDefault}
        points={path}
        fill="var(--color-brand-500)"
        fillOpacity={0.1}
        stroke="var(--color-brand-500)"
        strokeWidth={1.1}
        strokeLinejoin="round"
      />

      {/* Sides drawn individually on top, so one can be emphasised alone. */}
      {points.map((point, i) => {
        const next = points[(i + 1) % points.length]
        const name = `${spec.vertices[i] ?? ''}${spec.vertices[(i + 1) % points.length] ?? ''}`
        if (!shows(name)) return null
        const active = emphasises(name)
        const mid = { x: (point.x + next.x) / 2, y: (point.y + next.y) / 2 }
        const away = pushOut(mid, centre, 4.5)

        return (
          <g key={name || i}>
            {active && (
              <line
                x1={point.x}
                y1={point.y}
                x2={next.x}
                y2={next.y}
                stroke="var(--color-brand-300)"
                strokeWidth={2}
                strokeLinecap="round"
              />
            )}
            {spec.show_sides && spec.sides[i] !== undefined && (
              <text
                x={away.x}
                y={away.y}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={3.6}
                fontWeight={active ? 600 : 400}
                fill={active ? 'var(--color-brand-300)' : 'var(--color-fg-muted)'}
                fontFamily="var(--font-sans)"
              >
                {spec.sides[i]}
              </text>
            )}
          </g>
        )
      })}

      {points.map((point, i) => {
        const name = spec.vertices[i] ?? String.fromCharCode(65 + i)
        if (!shows(name)) return null
        const active = emphasises(name) || emphasises(`angle:${name}`)
        const label = pushOut(point, centre, -5)

        return (
          <g key={`v-${name}`}>
            <circle
              cx={point.x}
              cy={point.y}
              r={active ? 1.8 : 1.2}
              fill={active ? 'var(--color-brand-300)' : 'var(--color-brand-500)'}
            />
            <text
              x={label.x}
              y={label.y}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={4}
              fontWeight={600}
              fill="var(--color-fg)"
              fontFamily="var(--font-sans)"
            >
              {name}
            </text>
            {spec.show_angles && (
              <text
                x={pushOut(point, centre, 6).x}
                y={pushOut(point, centre, 6).y}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={3.2}
                fill="var(--color-fg-subtle)"
                fontFamily="var(--font-sans)"
              >
                {Math.round(angles[i])}°
              </text>
            )}
          </g>
        )
      })}

      <Annotations spec={spec} points={points} centre={centre} />
    </>
  )
}

function rawPoints(spec: GeometrySpec): Point[] {
  switch (spec.shape) {
    case 'triangle':
      return triangleFromSides(spec.sides)
    case 'rectangle':
      return rectangleFromSides(spec.sides)
    default:
      return regularPolygon(Math.max(spec.vertices.length, 3))
  }
}

function centroid(points: Point[]): Point {
  if (points.length === 0) return { x: VIEW / 2, y: VIEW / 2 }
  return {
    x: points.reduce((sum, p) => sum + p.x, 0) / points.length,
    y: points.reduce((sum, p) => sum + p.y, 0) / points.length,
  }
}

/** Move `point` away from `from` by `distance` (negative moves further out). */
function pushOut(point: Point, from: Point, distance: number): Point {
  const dx = point.x - from.x
  const dy = point.y - from.y
  const length = Math.hypot(dx, dy) || 1
  return {
    x: point.x + (dx / length) * -distance,
    y: point.y + (dy / length) * -distance,
  }
}

/** Free-text notes attached to a vertex, a side, or the centre. */
function Annotations({
  spec,
  points,
  centre,
}: {
  spec: GeometrySpec
  points: Point[]
  centre: Point
}) {
  return (
    <>
      {spec.annotations.map((annotation, i) => {
        const at = anchorFor(annotation.at, spec.vertices, points) ?? centre
        return (
          <text
            key={`${annotation.at}-${i}`}
            x={at.x}
            y={at.y}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={3.2}
            fill="var(--color-fg-subtle)"
            fontFamily="var(--font-sans)"
          >
            {annotation.text}
          </text>
        )
      })}
    </>
  )
}

function anchorFor(at: string, vertices: string[], points: Point[]): Point | null {
  if (points.length === 0) return null

  const single = vertices.indexOf(at)
  if (single !== -1) return points[single]

  // A side is named by its two endpoints, e.g. "AB".
  if (at.length === 2) {
    const a = vertices.indexOf(at[0])
    const b = vertices.indexOf(at[1])
    if (a !== -1 && b !== -1) {
      return { x: (points[a].x + points[b].x) / 2, y: (points[a].y + points[b].y) / 2 }
    }
  }
  return null
}
