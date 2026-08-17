import { useMemo } from 'react'
import { motion } from 'motion/react'
import type { GraphDiagram as GraphSpec } from '../../api'
import { layoutGraph } from './layout'
import { toneFill, toneOn } from './tones'
import type { StepState } from './useDiagramSteps'
import { springDefault } from '../../motion/springs'

interface Props {
  spec: GraphSpec
  steps: StepState
}

const NODE_W = 22
const NODE_H = 10
const MAX_CHARS = 13

/**
 * Nodes joined by edges: pipelines, binary trees, graphs, state machines.
 *
 * The four layouts share this renderer because the payload is identical in each
 * case — only the coordinates differ, and those come from layout.ts. That also
 * leaves the model one fewer decision to get wrong than four separate kinds
 * would.
 *
 * Edges are drawn before nodes so a line never crosses a label, and arrowheads
 * are drawn as explicit polygons rather than a <marker>, because a marker
 * inherits neither the edge's emphasis state nor a var() stroke reliably.
 */
export default function GraphDiagram({ spec, steps }: Props) {
  const placed = useMemo(() => layoutGraph(spec), [spec])
  const byId = useMemo(() => new Map(placed.map((n) => [n.id, n])), [placed])

  const gated = steps.visible.size > 0
  const shows = (id: string) => !gated || steps.visible.has(id)
  const emphasises = (id: string) => steps.active.has(id)

  return (
    <>
      {spec.edges.map((edge) => {
        const from = byId.get(edge.from)
        const to = byId.get(edge.to)
        if (!from || !to) return null

        const id = `${edge.from}->${edge.to}`
        // An edge is only as visible as the nodes it joins; drawing a line to a
        // box that has not appeared yet is worse than drawing nothing.
        if (!shows(id) || !shows(edge.from) || !shows(edge.to)) return null

        const active = emphasises(id)
        const [start, end] = trimToBoxes(from, to)
        const stroke = active ? 'var(--color-brand-400)' : 'var(--color-border-strong)'

        return (
          <motion.g
            key={id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={springDefault}
          >
            <line
              x1={start.x}
              y1={start.y}
              x2={end.x}
              y2={end.y}
              stroke={stroke}
              strokeWidth={active ? 1.1 : 0.7}
              strokeDasharray={edge.directed ? undefined : '2 1.6'}
            />
            {edge.directed && <Arrowhead from={start} to={end} fill={stroke} />}
            {edge.label && (
              <text
                x={(start.x + end.x) / 2}
                y={(start.y + end.y) / 2 - 1.4}
                textAnchor="middle"
                fontSize={3}
                fill="var(--color-fg-subtle)"
                fontFamily="var(--font-sans)"
              >
                {truncate(edge.label, 18)}
              </text>
            )}
          </motion.g>
        )
      })}

      {placed.map((node) => {
        if (!shows(node.id)) return null
        const active = emphasises(node.id)
        const tone = active ? 'brand' : node.tone
        const isNeutral = tone === 'neutral'

        return (
          <motion.g
            key={node.id}
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={springDefault}
            style={{ transformOrigin: `${node.x}px ${node.y}px` }}
          >
            <rect
              x={node.x - NODE_W / 2}
              y={node.y - NODE_H / 2}
              width={NODE_W}
              height={NODE_H}
              rx={2.2}
              fill={isNeutral ? 'var(--color-surface)' : toneFill(tone)}
              stroke={isNeutral ? 'var(--color-border)' : 'none'}
              strokeWidth={0.6}
            />
            <text
              x={node.x}
              y={node.y}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={3.4}
              fontWeight={500}
              fill={isNeutral ? 'var(--color-fg)' : toneOn(tone)}
              fontFamily="var(--font-sans)"
            >
              {truncate(node.label, MAX_CHARS)}
            </text>
          </motion.g>
        )
      })}
    </>
  )
}

/** Stop the line at each box's edge so it does not run under the label. */
function trimToBoxes(
  from: { x: number; y: number },
  to: { x: number; y: number },
): [{ x: number; y: number }, { x: number; y: number }] {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const length = Math.hypot(dx, dy) || 1
  const ux = dx / length
  const uy = dy / length

  // Scale the unit vector out to whichever box face it crosses first.
  const reach = (u: number, v: number) => {
    const tx = u !== 0 ? (NODE_W / 2 + 1) / Math.abs(u) : Infinity
    const ty = v !== 0 ? (NODE_H / 2 + 1) / Math.abs(v) : Infinity
    return Math.min(tx, ty)
  }
  const out = reach(ux, uy)
  return [
    { x: from.x + ux * out, y: from.y + uy * out },
    { x: to.x - ux * out, y: to.y - uy * out },
  ]
}

function Arrowhead({
  from,
  to,
  fill,
}: {
  from: { x: number; y: number }
  to: { x: number; y: number }
  fill: string
}) {
  const angle = Math.atan2(to.y - from.y, to.x - from.x)
  const size = 2
  const wing = 0.5
  const point = (offset: number, spread: number) => {
    const a = angle + offset
    return `${to.x - Math.cos(a) * spread},${to.y - Math.sin(a) * spread}`
  }
  return (
    <polygon
      points={`${to.x},${to.y} ${point(wing, size)} ${point(-wing, size)}`}
      fill={fill}
    />
  )
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}
