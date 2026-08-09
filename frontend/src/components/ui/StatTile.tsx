import { useEffect } from 'react'
import { motion, useMotionValue, useSpring, useTransform, useReducedMotion } from 'motion/react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'
import IconBadge, { type Tone } from './IconBadge'

interface StatTileProps {
  icon: LucideIcon
  label: string
  value: number | string
  unit?: string
  tone?: Tone
  countUp?: boolean
  hint?: string
  className?: string
}

function CountUp({ value }: { value: number }) {
  const mv = useMotionValue(0)
  const spring = useSpring(mv, { bounce: 0, duration: 0.9 })
  const rounded = useTransform(spring, (v) => Math.round(v).toLocaleString())

  useEffect(() => {
    mv.set(value)
  }, [mv, value])

  return <motion.span>{rounded}</motion.span>
}

export default function StatTile({
  icon,
  label,
  value,
  unit,
  tone = 'brand',
  countUp = false,
  hint,
  className,
}: StatTileProps) {
  const reduced = useReducedMotion()
  const animate = countUp && !reduced && typeof value === 'number'

  return (
    <div
      className={cn('rounded-lg border border-border bg-surface p-4 shadow-e1', className)}
    >
      <IconBadge icon={icon} tone={tone} size="md" className="mb-3" />
      <p className="text-title-lg text-fg tabular-nums">
        {animate ? <CountUp value={value as number} /> : value}
        {unit && <span className="text-headline text-fg-subtle ml-0.5">{unit}</span>}
      </p>
      <p className="text-caption text-fg-subtle mt-0.5">{label}</p>
      {hint && <p className="text-caption text-fg-faint mt-1">{hint}</p>}
    </div>
  )
}
