import { motion } from 'motion/react'
import type { BoardDiagram as BoardSpec } from '../../api'
import { VIEW } from './layout'
import { toneFill, toneOn } from './tones'
import type { StepState } from './useDiagramSteps'
import { springDefault } from '../../motion/springs'

interface Props {
  spec: BoardSpec
  steps: StepState
}

const LABEL_BAND = 8

/**
 * A square grid: chessboard, coordinate grid, matrix.
 *
 * Squares are addressed algebraically ("d4") and that is also the element id a
 * step references, so a caption saying "the knight reaches e6" and the square
 * that lights up cannot drift apart.
 *
 * The light/dark squares use canvas-elevated against surface-raised rather than
 * the traditional cream-and-brown. Those two tokens keep their contrast
 * relationship in both themes, where a fixed pair would invert in one of them.
 */
export default function BoardDiagram({ spec, steps }: Props) {
  const { size, labels } = spec
  const offset = labels ? LABEL_BAND : 0
  const board = VIEW - offset
  const cell = board / size

  // Rank 1 sits at the bottom, as on a real board.
  const toXY = (file: number, rank: number) => ({
    x: offset + file * cell,
    y: (size - 1 - rank) * cell,
  })
  const parse = (square: string) => ({
    file: square.charCodeAt(0) - 97,
    rank: Number(square.slice(1)) - 1,
  })

  // An empty visible set means the diagram is not gating on reveal.
  const gated = steps.visible.size > 0
  const shows = (id: string) => !gated || steps.visible.has(id)
  const emphasises = (id: string) => steps.active.has(id)

  const highlighted = new Set(spec.highlight)

  return (
    <>
      {Array.from({ length: size * size }, (_, i) => {
        const file = i % size
        const rank = Math.floor(i / size)
        const square = `${String.fromCharCode(97 + file)}${rank + 1}`
        const { x, y } = toXY(file, rank)
        const dark = (file + rank) % 2 === 0
        const lit = highlighted.has(square) && shows(square)
        const active = emphasises(square)

        return (
          <g key={square}>
            <rect
              x={x}
              y={y}
              width={cell}
              height={cell}
              fill={dark ? 'var(--color-surface-raised)' : 'var(--color-canvas)'}
            />
            {(lit || active) && (
              <motion.rect
                initial={{ opacity: 0 }}
                animate={{ opacity: active ? 0.85 : 0.45 }}
                transition={springDefault}
                x={x}
                y={y}
                width={cell}
                height={cell}
                fill="var(--color-brand-500)"
              />
            )}
            {active && (
              <rect
                x={x + 0.6}
                y={y + 0.6}
                width={cell - 1.2}
                height={cell - 1.2}
                fill="none"
                stroke="var(--color-brand-300)"
                strokeWidth={0.9}
              />
            )}
          </g>
        )
      })}

      {/* Grid lines last, so they sit above the tints and keep the cells crisp. */}
      <rect
        x={offset}
        y={0}
        width={board}
        height={board}
        fill="none"
        stroke="var(--color-border)"
        strokeWidth={0.6}
      />

      {spec.pieces.map((piece) => {
        const { file, rank } = parse(piece.at)
        const { x, y } = toXY(file, rank)
        if (!shows(piece.at)) return null
        return (
          <motion.g
            key={piece.at}
            initial={{ opacity: 0, scale: 0.7 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={springDefault}
            style={{ transformOrigin: `${x + cell / 2}px ${y + cell / 2}px` }}
          >
            <circle
              cx={x + cell / 2}
              cy={y + cell / 2}
              r={cell * 0.34}
              fill={toneFill(piece.tone === 'neutral' ? 'brand' : piece.tone)}
            />
            <text
              x={x + cell / 2}
              y={y + cell / 2}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={cell * 0.4}
              fontWeight={600}
              fill={toneOn(piece.tone === 'neutral' ? 'brand' : piece.tone)}
              fontFamily="var(--font-sans)"
            >
              {piece.glyph}
            </text>
          </motion.g>
        )
      })}

      {labels && (
        <g fill="var(--color-fg-faint)" fontSize={LABEL_BAND * 0.52} fontFamily="var(--font-sans)">
          {Array.from({ length: size }, (_, i) => (
            <text
              key={`file-${i}`}
              x={offset + i * cell + cell / 2}
              y={board + LABEL_BAND * 0.62}
              textAnchor="middle"
            >
              {String.fromCharCode(97 + i)}
            </text>
          ))}
          {Array.from({ length: size }, (_, i) => (
            <text
              key={`rank-${i}`}
              x={offset * 0.45}
              y={(size - 1 - i) * cell + cell / 2}
              textAnchor="middle"
              dominantBaseline="central"
            >
              {i + 1}
            </text>
          ))}
        </g>
      )}
    </>
  )
}
