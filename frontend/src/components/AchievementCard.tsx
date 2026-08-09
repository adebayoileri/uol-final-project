import { Check, Lock } from 'lucide-react'
import { cn } from '../lib/cn'

interface AchievementCardProps {
  title: string
  description: string
  icon: string
  unlocked: boolean
  unlocked_at?: string | null
}

export default function AchievementCard({
  title,
  description,
  icon,
  unlocked,
  unlocked_at,
}: AchievementCardProps) {
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg border p-4 transition-colors',
        unlocked
          ? 'border-brand-500/40 bg-brand-500/8'
          : 'border-border bg-surface',
      )}
    >
      <span
        className={cn(
          'grid size-10 shrink-0 place-items-center rounded-lg text-xl',
          unlocked ? 'bg-brand-500/15' : 'bg-surface-raised grayscale',
        )}
        aria-hidden="true"
      >
        {icon}
      </span>

      <div className="min-w-0 flex-1">
        <p className={cn('text-callout font-medium', unlocked ? 'text-fg' : 'text-fg-subtle')}>
          {title}
        </p>
        <p className="text-caption text-fg-subtle mt-0.5">{description}</p>
        {unlocked && unlocked_at && (
          <p className="text-caption text-brand-300 mt-1.5">
            Unlocked {new Date(unlocked_at).toLocaleDateString()}
          </p>
        )}
      </div>

      {/* Locked state is stated, not just implied by lower opacity. */}
      {unlocked ? (
        <Check size={16} className="text-brand-300 mt-0.5 shrink-0" aria-label="Unlocked" />
      ) : (
        <Lock size={14} className="text-fg-faint mt-0.5 shrink-0" aria-label="Locked" />
      )}
    </div>
  )
}
