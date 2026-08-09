import { motion, useReducedMotion } from 'motion/react'

const COLORS = [
  'var(--color-brand-400)',
  'var(--color-success)',
  'var(--color-warn)',
  'var(--color-info)',
]

/**
 * One-shot celebration burst. Suppressed entirely under reduced motion —
 * this is decoration, so the gentler equivalent is nothing at all.
 */
export default function Confetti({ count = 14 }: { count?: number }) {
  const reduced = useReducedMotion()
  if (reduced) return null

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => {
        const angle = (i / count) * Math.PI * 2
        const distance = 90 + (i % 4) * 26
        return (
          <motion.span
            key={i}
            className="absolute top-1/2 left-1/2 size-1.5 rounded-full"
            style={{ background: COLORS[i % COLORS.length] }}
            initial={{ x: 0, y: 0, opacity: 1, scale: 1 }}
            animate={{
              x: Math.cos(angle) * distance,
              y: Math.sin(angle) * distance + 40,
              opacity: 0,
              scale: 0.4,
            }}
            transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1], delay: (i % 5) * 0.03 }}
          />
        )
      })}
    </div>
  )
}
