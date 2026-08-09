import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'
import type { Tone } from './IconBadge'

const TONES: Record<Tone, string> = {
  brand: 'bg-brand-500/12 text-brand-300 border-brand-500/25',
  success: 'bg-success/12 text-success border-success/25',
  warn: 'bg-warn/12 text-warn border-warn/25',
  danger: 'bg-danger/12 text-danger border-danger/25',
  info: 'bg-info/12 text-info border-info/25',
  neutral: 'bg-surface-raised text-fg-subtle border-border',
}

const SIZES = {
  sm: 'text-eyebrow px-1.5 py-0.5 gap-1',
  md: 'text-caption px-2 py-0.5 gap-1.5',
} as const

interface BadgeProps {
  tone?: Tone
  size?: keyof typeof SIZES
  icon?: LucideIcon
  dot?: boolean
  className?: string
  children: React.ReactNode
}

export default function Badge({
  tone = 'neutral',
  size = 'md',
  icon: Icon,
  dot = false,
  className,
  children,
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border font-medium whitespace-nowrap',
        SIZES[size],
        TONES[tone],
        className,
      )}
    >
      {dot && <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />}
      {Icon && <Icon size={size === 'sm' ? 11 : 13} aria-hidden="true" />}
      {children}
    </span>
  )
}
