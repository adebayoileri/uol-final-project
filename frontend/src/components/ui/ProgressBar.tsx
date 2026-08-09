import { motion, useReducedMotion } from 'motion/react'
import { cn } from '../../lib/cn'
import { springDefault } from '../../motion/springs'
import type { Tone } from './IconBadge'

const SIZES = {
  xs: 'h-1',
  sm: 'h-1.5',
  md: 'h-2.5',
} as const

const FILL: Record<Tone, string> = {
  brand: 'bg-brand-500',
  success: 'bg-success',
  warn: 'bg-warn',
  danger: 'bg-danger',
  info: 'bg-info',
  neutral: 'bg-fg-subtle',
}

interface ProgressBarProps {
  /** 0–1 */
  value: number
  size?: keyof typeof SIZES
  tone?: Tone
  label?: string
  /** Keep `label` for assistive tech but don't render the row above the bar. */
  hideLabel?: boolean
  showValue?: boolean
  className?: string
}

export default function ProgressBar({
  value,
  size = 'sm',
  tone = 'brand',
  label,
  hideLabel = false,
  showValue = false,
  className,
}: ProgressBarProps) {
  const reduced = useReducedMotion()
  const clamped = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0))
  const pct = Math.round(clamped * 100)

  return (
    <div className={cn('w-full', className)}>
      {((label && !hideLabel) || showValue) && (
        <div className="mb-1.5 flex items-baseline justify-between gap-3">
          {label && !hideLabel ? (
            <span className="text-caption text-fg-muted truncate">{label}</span>
          ) : (
            <span />
          )}
          {showValue && (
            <span className="text-caption text-fg-subtle tabular-nums shrink-0">{pct}%</span>
          )}
        </div>
      )}
      <div
        className={cn('w-full overflow-hidden rounded-full bg-surface-raised', SIZES[size])}
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? 'Progress'}
      >
        {/* scaleX rather than width: transform stays on the compositor. */}
        <motion.div
          className={cn('h-full origin-left rounded-full', FILL[tone])}
          initial={reduced ? false : { scaleX: 0 }}
          animate={{ scaleX: clamped }}
          transition={springDefault}
          style={{ width: '100%' }}
        />
      </div>
    </div>
  )
}
