import { cn } from '../../lib/cn'

const SHIMMER =
  'relative overflow-hidden bg-surface-raised before:absolute before:inset-0 ' +
  'before:animate-shimmer before:bg-[linear-gradient(90deg,transparent,rgb(255_255_255/0.045),transparent)] ' +
  'before:bg-[length:180%_100%]'

interface SkeletonProps {
  variant?: 'text' | 'title' | 'block' | 'circle'
  lines?: number
  width?: string
  height?: string
  className?: string
}

/**
 * A skeleton earns its place only if it occupies the same box as the content it
 * stands in for — otherwise it trades a blank screen for a layout shift.
 */
export default function Skeleton({
  variant = 'text',
  lines = 1,
  width,
  height,
  className,
}: SkeletonProps) {
  if (variant === 'circle') {
    return (
      <div
        className={cn(SHIMMER, 'rounded-full', className)}
        style={{ width: width ?? '2.5rem', height: height ?? width ?? '2.5rem' }}
        aria-hidden="true"
      />
    )
  }

  if (variant === 'block') {
    return (
      <div
        className={cn(SHIMMER, 'rounded-lg', className)}
        style={{ width, height: height ?? '6rem' }}
        aria-hidden="true"
      />
    )
  }

  const h = variant === 'title' ? 'h-6' : 'h-3.5'

  return (
    <div className={cn('space-y-2', className)} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={cn(SHIMMER, 'rounded', h)}
          style={{ width: i === lines - 1 && lines > 1 ? '70%' : (width ?? '100%') }}
        />
      ))}
    </div>
  )
}

/** Matches the CourseLibrary card grid. */
export function CardListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-lg border border-border bg-surface p-4">
          <div className="mb-3 flex items-start justify-between gap-3">
            <Skeleton variant="title" width="60%" />
            <Skeleton width="4rem" className="mt-1" />
          </div>
          <Skeleton lines={2} className="mb-4" />
          <Skeleton variant="block" height="0.375rem" className="rounded-full" />
        </div>
      ))}
    </div>
  )
}

/** Matches the LessonView reading column. */
export function LessonSkeleton() {
  return (
    <div className="space-y-8" aria-busy="true" aria-label="Loading lesson">
      <div className="space-y-3">
        <Skeleton width="12rem" />
        <Skeleton variant="title" width="70%" height="2.25rem" />
        <Skeleton variant="block" height="3.5rem" />
      </div>
      <Skeleton variant="block" height="8rem" />
      <div className="space-y-3">
        <Skeleton lines={4} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Skeleton variant="block" height="6rem" />
        <Skeleton variant="block" height="6rem" />
      </div>
    </div>
  )
}

/** Matches a stat-tile row plus a content block. */
export function DashboardSkeleton({ tiles = 3 }: { tiles?: number }) {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading">
      <div className="space-y-3">
        <Skeleton width="8rem" />
        <Skeleton variant="title" width="45%" height="2.5rem" />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {Array.from({ length: tiles }).map((_, i) => (
          <Skeleton key={i} variant="block" height="6.5rem" />
        ))}
      </div>
      <Skeleton variant="block" height="16rem" />
    </div>
  )
}
