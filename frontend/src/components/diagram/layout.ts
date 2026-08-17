/**
 * Diagram geometry. Pure functions, no React, no DOM.
 *
 * This file is the half of the feature the model does not write. It takes a
 * semantic spec — "a chain of three nodes", "sides 3, 4 and 5" — and produces
 * coordinates in a fixed viewBox space. Keeping it separate from the renderers
 * is what makes the layout arguable on its own terms: none of it depends on
 * theme, motion, or React lifecycle.
 *
 * Everything works in a 0..VIEW coordinate space and is scaled by the SVG
 * viewBox, so nothing here needs to know the rendered size.
 */

import type { GraphDiagram, GraphEdge, PlotSeries } from '../../api'

export const VIEW = 100

export interface Point {
  x: number
  y: number
}

export interface PlacedNode extends Point {
  id: string
  label: string
  tone: string
}

// ── graphs ───────────────────────────────────────────────────────────────────

/** Children of each node, in the order their edges were declared. */
function childMap(edges: GraphEdge[]): Map<string, string[]> {
  const children = new Map<string, string[]>()
  for (const edge of edges) {
    const list = children.get(edge.from) ?? []
    list.push(edge.to)
    children.set(edge.from, list)
  }
  return children
}

function rootOf(diagram: GraphDiagram): string {
  const hasParent = new Set(diagram.edges.map((e) => e.to))
  const root = diagram.nodes.find((n) => !hasParent.has(n.id))
  // The backend guarantees exactly one root for tree layouts. Falling back to
  // the first node keeps a hand-written or future spec from rendering blank.
  return root?.id ?? diagram.nodes[0].id
}

/**
 * Tidy-ish tree layout: x from in-order position among leaves, y from depth.
 *
 * Not Reingold–Tilford — a parent sits at the midpoint of its children rather
 * than being threaded against its siblings' contours. For the 3-15 node trees
 * a lesson actually uses, the difference is invisible and the algorithm stays
 * short enough to read.
 */
function treeLayout(diagram: GraphDiagram): PlacedNode[] {
  const children = childMap(diagram.edges)
  const xs = new Map<string, number>()
  const depths = new Map<string, number>()

  let nextLeafX = 0
  let maxDepth = 0

  // Iterative post-order: a deep tree should not be able to blow the stack,
  // and recursion here would also make cycle-guarding harder to see.
  const stack: { id: string; depth: number; expanded: boolean }[] = [
    { id: rootOf(diagram), depth: 0, expanded: false },
  ]
  const seen = new Set<string>()

  while (stack.length > 0) {
    const frame = stack.pop()!
    const kids = (children.get(frame.id) ?? []).filter((k) => !seen.has(k))

    if (!frame.expanded) {
      if (seen.has(frame.id)) continue
      seen.add(frame.id)
      depths.set(frame.id, frame.depth)
      maxDepth = Math.max(maxDepth, frame.depth)

      if (kids.length === 0) {
        xs.set(frame.id, nextLeafX++)
        continue
      }
      stack.push({ ...frame, expanded: true })
      // Reversed so the first-declared child is popped first and lands leftmost.
      for (let i = kids.length - 1; i >= 0; i--) {
        stack.push({ id: kids[i], depth: frame.depth + 1, expanded: false })
      }
      continue
    }

    const placed = (children.get(frame.id) ?? [])
      .map((k) => xs.get(k))
      .filter((v): v is number => v !== undefined)
    xs.set(frame.id, placed.length ? (Math.min(...placed) + Math.max(...placed)) / 2 : nextLeafX++)
  }

  // Any node unreachable from the root still has to go somewhere visible.
  for (const node of diagram.nodes) {
    if (!xs.has(node.id)) {
      xs.set(node.id, nextLeafX++)
      depths.set(node.id, maxDepth)
    }
  }

  const columns = Math.max(nextLeafX - 1, 1)
  const rows = Math.max(maxDepth, 1)
  return diagram.nodes.map((n) => ({
    id: n.id,
    label: n.label,
    tone: n.tone,
    x: pad((xs.get(n.id) ?? 0) / columns),
    y: pad((depths.get(n.id) ?? 0) / rows),
  }))
}

/** Follow the single path from its start, so display order is stage order. */
function chainLayout(diagram: GraphDiagram): PlacedNode[] {
  const next = new Map(diagram.edges.map((e) => [e.from, e.to]))
  const hasParent = new Set(diagram.edges.map((e) => e.to))
  const start = diagram.nodes.find((n) => !hasParent.has(n.id)) ?? diagram.nodes[0]

  const order: string[] = []
  const seen = new Set<string>()
  let cursor: string | undefined = start.id
  while (cursor && !seen.has(cursor)) {
    seen.add(cursor)
    order.push(cursor)
    cursor = next.get(cursor)
  }
  for (const node of diagram.nodes) if (!seen.has(node.id)) order.push(node.id)

  const byId = new Map(diagram.nodes.map((n) => [n.id, n]))
  const span = Math.max(order.length - 1, 1)
  // Vertical past four stages: labels are words, and four boxes across is
  // already tight at the width a lesson column actually gets.
  const vertical = order.length > 4
  return order.map((id, i) => {
    const node = byId.get(id)!
    return {
      id,
      label: node.label,
      tone: node.tone,
      x: vertical ? pad(0.5) : pad(i / span),
      y: vertical ? pad(i / span) : pad(0.5),
    }
  })
}

/**
 * Longest-path layering for a directed graph: rank = distance from a source.
 *
 * Deterministic, unlike force-directed, which matters because the same lesson
 * must draw the same picture every open.
 */
function layeredLayout(diagram: GraphDiagram): PlacedNode[] {
  const children = childMap(diagram.edges)
  const indegree = new Map(diagram.nodes.map((n) => [n.id, 0]))
  for (const edge of diagram.edges) {
    indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1)
  }

  const rank = new Map(diagram.nodes.map((n) => [n.id, 0]))
  const queue = diagram.nodes.filter((n) => indegree.get(n.id) === 0).map((n) => n.id)
  const processed = new Set<string>(queue)

  while (queue.length > 0) {
    const id = queue.shift()!
    for (const child of children.get(id) ?? []) {
      rank.set(child, Math.max(rank.get(child) ?? 0, (rank.get(id) ?? 0) + 1))
      const remaining = (indegree.get(child) ?? 1) - 1
      indegree.set(child, remaining)
      if (remaining === 0 && !processed.has(child)) {
        processed.add(child)
        queue.push(child)
      }
    }
  }

  // A cycle leaves nodes unprocessed. Rather than fail, park them one rank past
  // everything else — a cyclic graph is legal input for a `layered` spec.
  const maxRank = Math.max(0, ...[...rank.values()])
  for (const node of diagram.nodes) {
    if (!processed.has(node.id)) rank.set(node.id, maxRank + 1)
  }

  const byRank = new Map<number, string[]>()
  for (const node of diagram.nodes) {
    const r = rank.get(node.id) ?? 0
    byRank.set(r, [...(byRank.get(r) ?? []), node.id])
  }

  const ranks = Math.max(...byRank.keys(), 1)
  const byId = new Map(diagram.nodes.map((n) => [n.id, n]))
  const placed: PlacedNode[] = []
  for (const [r, ids] of byRank) {
    ids.forEach((id, i) => {
      const node = byId.get(id)!
      placed.push({
        id,
        label: node.label,
        tone: node.tone,
        x: pad(ids.length === 1 ? 0.5 : i / (ids.length - 1)),
        y: pad(r / ranks),
      })
    })
  }
  return placed
}

/** Evenly around a circle, starting at twelve o'clock. */
function circularLayout(diagram: GraphDiagram): PlacedNode[] {
  const count = diagram.nodes.length
  const radius = VIEW * 0.34
  return diagram.nodes.map((node, i) => {
    const angle = (i / count) * Math.PI * 2 - Math.PI / 2
    return {
      id: node.id,
      label: node.label,
      tone: node.tone,
      x: VIEW / 2 + Math.cos(angle) * radius,
      y: VIEW / 2 + Math.sin(angle) * radius,
    }
  })
}

/** Map a 0..1 fraction into the drawable band, leaving room for node boxes. */
function pad(fraction: number): number {
  const margin = 14
  return margin + fraction * (VIEW - margin * 2)
}

export function layoutGraph(diagram: GraphDiagram): PlacedNode[] {
  switch (diagram.layout) {
    case 'tree':
      return treeLayout(diagram)
    case 'chain':
      return chainLayout(diagram)
    case 'circular':
      return circularLayout(diagram)
    default:
      return layeredLayout(diagram)
  }
}

// ── geometry ─────────────────────────────────────────────────────────────────

/**
 * Triangle vertices from three side lengths, by the law of cosines.
 *
 * A is at the origin and B along the x-axis; C is found from the angle at A.
 * The caller has already been guaranteed these sides can close — the backend
 * rejects anything violating the triangle inequality — so this cannot produce
 * a NaN from an out-of-domain acos.
 */
export function triangleFromSides([a, b, c]: number[]): Point[] {
  // a = BC (opposite A), b = CA (opposite B), c = AB (opposite C).
  const cosA = (b * b + c * c - a * a) / (2 * b * c)
  const angleA = Math.acos(Math.min(1, Math.max(-1, cosA)))
  return [
    { x: 0, y: 0 },
    { x: c, y: 0 },
    { x: b * Math.cos(angleA), y: b * Math.sin(angleA) },
  ]
}

export function rectangleFromSides([width, height]: number[]): Point[] {
  return [
    { x: 0, y: 0 },
    { x: width, y: 0 },
    { x: width, y: height },
    { x: 0, y: height },
  ]
}

/** A regular n-gon, flat-topped enough to read, on the unit circle. */
export function regularPolygon(count: number): Point[] {
  return Array.from({ length: count }, (_, i) => {
    const angle = (i / count) * Math.PI * 2 - Math.PI / 2
    return { x: Math.cos(angle), y: Math.sin(angle) }
  })
}

/**
 * Scale and centre arbitrary points into the viewBox, flipping y.
 *
 * SVG's y grows downward; every shape above is expressed in maths convention
 * where it grows upward, so this is the single place that inversion happens.
 */
export function fitPoints(points: Point[], margin = 16): Point[] {
  if (points.length === 0) return []
  const xs = points.map((p) => p.x)
  const ys = points.map((p) => p.y)
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  const width = Math.max(...xs) - minX
  const height = Math.max(...ys) - minY
  const span = VIEW - margin * 2
  // A degenerate axis (a flat shape) must not divide by zero.
  const scale = Math.min(width > 0 ? span / width : span, height > 0 ? span / height : span)

  const offsetX = (VIEW - width * scale) / 2
  const offsetY = (VIEW - height * scale) / 2
  return points.map((p) => ({
    x: offsetX + (p.x - minX) * scale,
    y: VIEW - (offsetY + (p.y - minY) * scale),
  }))
}

/** Interior angle at each vertex, in degrees, for a closed polygon. */
export function interiorAngles(points: Point[]): number[] {
  const count = points.length
  return points.map((point, i) => {
    const prev = points[(i - 1 + count) % count]
    const next = points[(i + 1) % count]
    const a = Math.atan2(prev.y - point.y, prev.x - point.x)
    const b = Math.atan2(next.y - point.y, next.x - point.x)
    let angle = Math.abs(a - b) * (180 / Math.PI)
    if (angle > 180) angle = 360 - angle
    return angle
  })
}

// ── plots ────────────────────────────────────────────────────────────────────

const SAMPLES = 96

/**
 * Evaluate a named curve family.
 *
 * A fixed menu rather than an expression the model writes: there is no path
 * here from generated text to anything executed.
 */
function evaluate(series: PlotSeries, x: number): number {
  const p = series.fn?.params ?? {}
  switch (series.fn?.family) {
    case 'linear':
      return (p.m ?? 1) * x + (p.c ?? 0)
    case 'quadratic':
      return (p.a ?? 1) * x * x + (p.b ?? 0) * x + (p.c ?? 0)
    case 'exponential':
      return (p.a ?? 1) * Math.exp((p.k ?? 1) * x)
    case 'sigmoid':
      return 1 / (1 + Math.exp(-(p.k ?? 1) * (x - (p.x0 ?? 0))))
    case 'sine':
      return (p.a ?? 1) * Math.sin((p.f ?? 1) * x + (p.phase ?? 0))
    case 'normal': {
      const mu = p.mu ?? 0
      const sigma = p.sigma ?? 1
      return Math.exp(-((x - mu) ** 2) / (2 * sigma * sigma)) / (sigma * Math.sqrt(2 * Math.PI))
    }
    default:
      return 0
  }
}

/** Sample a series into data-space points, dropping anything non-finite. */
export function sampleSeries(series: PlotSeries, [lo, hi]: [number, number]): Point[] {
  if (series.type !== 'function') {
    return (series.points ?? []).map(([x, y]) => ({ x, y }))
  }
  const points: Point[] = []
  for (let i = 0; i <= SAMPLES; i++) {
    const x = lo + ((hi - lo) * i) / SAMPLES
    const y = evaluate(series, x)
    // An exponential over a wide range overflows; dropping the point breaks the
    // path there rather than sending the whole curve to infinity.
    if (Number.isFinite(y)) points.push({ x, y })
  }
  return points
}

/** The y span to draw, from the spec if given or from the data if not. */
export function resolveYRange(
  declared: [number, number] | null,
  sampled: Point[][],
): [number, number] {
  if (declared) return declared
  const ys = sampled.flat().map((p) => p.y)
  if (ys.length === 0) return [0, 1]
  const lo = Math.min(...ys)
  const hi = Math.max(...ys)
  if (lo === hi) return [lo - 1, hi + 1]
  const headroom = (hi - lo) * 0.08
  return [lo - headroom, hi + headroom]
}

/** Data space -> view space, with y flipped. */
export function makeScale(
  [x0, x1]: [number, number],
  [y0, y1]: [number, number],
  margin = 16,
) {
  const span = VIEW - margin * 2
  return (point: Point): Point => ({
    x: margin + ((point.x - x0) / (x1 - x0)) * span,
    y: VIEW - margin - ((point.y - y0) / (y1 - y0)) * span,
  })
}

/** Round numbers for an axis label without trailing float noise. */
export function axisLabel(value: number): string {
  if (Object.is(value, -0) || Math.abs(value) < 1e-9) return '0'
  const abs = Math.abs(value)
  const digits = abs >= 100 ? 0 : abs >= 10 ? 1 : 2
  return Number(value.toFixed(digits)).toString()
}
