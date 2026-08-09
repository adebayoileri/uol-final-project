import { cn } from '../../lib/cn'

interface SectionHeadingProps {
  title: string
  count?: number
  description?: string
  action?: React.ReactNode
  level?: 2 | 3
  className?: string
}

/**
 * Section headings used to be `text-xs uppercase text-gray-500` — the smallest,
 * lowest-contrast text on their own page. They now carry real weight.
 */
export default function SectionHeading({
  title,
  count,
  description,
  action,
  level = 2,
  className,
}: SectionHeadingProps) {
  const Tag = level === 2 ? 'h2' : 'h3'
  return (
    <div className={cn('flex items-end justify-between gap-4', className)}>
      <div className="min-w-0">
        <Tag className="text-headline text-fg">
          {title}
          {count !== undefined && (
            <span className="text-fg-faint ml-2 tabular-nums">{count}</span>
          )}
        </Tag>
        {description && <p className="text-caption text-fg-subtle mt-1">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

/** A genuine over-line label, e.g. above a title. Not a section heading. */
export function Eyebrow({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={cn('text-eyebrow text-fg-subtle uppercase', className)}>{children}</p>
  )
}
