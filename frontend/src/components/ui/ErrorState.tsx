import { AlertTriangle, RotateCcw } from 'lucide-react'
import { cn } from '../../lib/cn'
import Button, { ButtonLink } from './Button'
import IconBadge from './IconBadge'

interface ErrorStateProps {
  title?: string
  message: string
  onRetry?: () => void
  backTo?: string
  backLabel?: string
  /** Compact form for use inside a card, rather than as a page takeover. */
  inline?: boolean
  className?: string
}

/**
 * Every error surface offers a retry and a way out — an error that only tells
 * you something failed leaves the user stranded.
 */
export default function ErrorState({
  title = 'Something went wrong',
  message,
  onRetry,
  backTo,
  backLabel = 'Go back',
  inline = false,
  className,
}: ErrorStateProps) {
  if (inline) {
    return (
      <div
        role="alert"
        className={cn(
          'flex items-start gap-3 rounded-md border border-danger/40 bg-danger/10 px-4 py-3',
          className,
        )}
      >
        <AlertTriangle size={16} className="text-danger mt-0.5 shrink-0" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-callout text-danger">{message}</p>
          {onRetry && (
            <Button variant="link" size="sm" onClick={onRetry} className="mt-1">
              Try again
            </Button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div
      role="alert"
      className={cn('flex flex-col items-center py-16 px-6 text-center', className)}
    >
      <IconBadge icon={AlertTriangle} tone="danger" size="lg" className="mb-4" />
      <p className="text-title text-fg">{title}</p>
      <p className="text-body text-fg-muted mt-2 max-w-md">{message}</p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        {onRetry && (
          <Button icon={RotateCcw} onClick={onRetry}>
            Try again
          </Button>
        )}
        {backTo && (
          <ButtonLink variant="secondary" to={backTo}>
            {backLabel}
          </ButtonLink>
        )}
      </div>
    </div>
  )
}
