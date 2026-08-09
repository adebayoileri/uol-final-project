import { motion } from 'motion/react'
import { cn } from '../../lib/cn'
import { springDefault } from '../../motion/springs'

const ELEVATION = {
  0: '',
  1: 'shadow-e1',
  2: 'shadow-e2',
  3: 'shadow-e3',
} as const

const PADDING = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
} as const

interface CardProps {
  elevation?: keyof typeof ELEVATION
  padding?: keyof typeof PADDING
  interactive?: boolean
  className?: string
  children: React.ReactNode
}

export default function Card({
  elevation = 1,
  padding = 'md',
  interactive = false,
  className,
  children,
}: CardProps) {
  const classes = cn(
    'rounded-lg border border-border bg-surface',
    ELEVATION[elevation],
    PADDING[padding],
    interactive &&
      'transition-colors duration-[--duration-fast] hover:border-border-strong hover:bg-surface-raised',
    className,
  )

  if (!interactive) return <div className={classes}>{children}</div>

  return (
    <motion.div whileHover={{ y: -2 }} transition={springDefault} className={classes}>
      {children}
    </motion.div>
  )
}
