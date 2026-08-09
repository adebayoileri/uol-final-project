import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'

export type Tone = 'brand' | 'success' | 'warn' | 'danger' | 'info' | 'neutral'

export const TONE_BADGE: Record<Tone, string> = {
  brand: 'bg-brand-500/12 text-brand-300',
  success: 'bg-success/12 text-success',
  warn: 'bg-warn/12 text-warn',
  danger: 'bg-danger/12 text-danger',
  info: 'bg-info/12 text-info',
  neutral: 'bg-surface-raised text-fg-subtle',
}

const SIZES = {
  sm: { box: 'size-7 rounded-md', icon: 14 },
  md: { box: 'size-9 rounded-lg', icon: 18 },
  lg: { box: 'size-12 rounded-xl', icon: 24 },
  xl: { box: 'size-16 rounded-2xl', icon: 30 },
} as const

interface IconBadgeProps {
  icon: LucideIcon
  tone?: Tone
  size?: keyof typeof SIZES
  className?: string
}

export default function IconBadge({
  icon: Icon,
  tone = 'brand',
  size = 'md',
  className,
}: IconBadgeProps) {
  const s = SIZES[size]
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center',
        s.box,
        TONE_BADGE[tone],
        className,
      )}
      aria-hidden="true"
    >
      <Icon size={s.icon} strokeWidth={2} />
    </span>
  )
}
