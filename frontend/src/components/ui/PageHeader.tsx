import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { cn } from '../../lib/cn'

interface PageHeaderProps {
  eyebrow?: string
  title: string
  description?: string
  actions?: React.ReactNode
  backTo?: string
  backLabel?: string
  /** `display` for top-level destinations, `title` for nested pages. */
  size?: 'display' | 'title'
  className?: string
}

/**
 * One h1 treatment and one back-link treatment for the whole app. Previously
 * every page invented its own, and back links were sub-12px grey text with no
 * tap target.
 */
export default function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  backTo,
  backLabel = 'Back',
  size = 'display',
  className,
}: PageHeaderProps) {
  return (
    <header className={cn('space-y-3', className)}>
      {backTo && (
        <Link
          to={backTo}
          className="text-callout text-fg-subtle hover:text-fg -ml-2 inline-flex min-h-11 items-center gap-1.5 rounded-md px-2 transition-colors"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          {backLabel}
        </Link>
      )}

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 flex-1">
          {eyebrow && (
            <p className="text-eyebrow text-brand-300 mb-1.5 uppercase">{eyebrow}</p>
          )}
          <h1
            className={cn(
              'text-fg text-balance',
              size === 'display' ? 'text-display-lg' : 'text-title-lg',
            )}
          >
            {title}
          </h1>
          {description && (
            <p className="text-body text-fg-muted mt-2 max-w-2xl text-pretty">{description}</p>
          )}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  )
}
