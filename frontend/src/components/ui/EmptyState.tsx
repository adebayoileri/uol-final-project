import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'
import IconBadge, { type Tone } from './IconBadge'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  tone?: Tone
  action?: React.ReactNode
  secondaryAction?: React.ReactNode
  compact?: boolean
  className?: string
}

export default function EmptyState({
  icon,
  title,
  description,
  tone = 'neutral',
  action,
  secondaryAction,
  compact = false,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center text-center',
        compact ? 'py-6' : 'py-16 px-6',
        className,
      )}
    >
      <IconBadge icon={icon} tone={tone} size={compact ? 'md' : 'lg'} className="mb-4" />
      <p className={cn('text-fg', compact ? 'text-callout font-medium' : 'text-title')}>{title}</p>
      {description && (
        <p className={cn('text-fg-muted mt-2 max-w-sm', compact ? 'text-caption' : 'text-body')}>
          {description}
        </p>
      )}
      {(action || secondaryAction) && (
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          {action}
          {secondaryAction}
        </div>
      )}
    </div>
  )
}
