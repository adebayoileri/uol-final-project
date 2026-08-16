import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { motion } from 'motion/react'
import {
  Ear,
  Grid3x3,
  ListOrdered,
  Lock,
  Mic,
  Play,
  Sparkles,
  type LucideIcon,
} from 'lucide-react'
import { getCourseDrills, type CourseDrills, type DrillKind } from '../api'
import {
  Badge,
  ButtonLink,
  Card,
  ErrorState,
  IconBadge,
  PageHeader,
  ProgressBar,
  Skeleton,
  type Tone,
} from '../components/ui'
import { listContainer, listItem } from '../motion/springs'
import { cn } from '../lib/cn'

const DRILL_VISUALS: Record<DrillKind, { icon: LucideIcon; tone: Tone }> = {
  mcq: { icon: Sparkles, tone: 'brand' },
  match: { icon: Grid3x3, tone: 'info' },
  order: { icon: ListOrdered, tone: 'warn' },
  listen: { icon: Ear, tone: 'success' },
  pronounce: { icon: Mic, tone: 'danger' },
}

export default function CourseDrills() {
  const { courseId } = useParams<{ courseId: string }>()
  const [data, setData] = useState<CourseDrills | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (!courseId) return
    setData(null)
    setError(null)
    getCourseDrills(courseId)
      .then(setData)
      .catch((err: Error) => setError(err.message))
  }, [courseId])

  useEffect(load, [load])

  if (!courseId) {
    return <ErrorState message="No course selected." backTo="/practice" backLabel="All practice" />
  }
  if (error) {
    return <ErrorState message={error} onRetry={load} backTo="/practice" backLabel="All practice" />
  }
  if (!data) {
    return (
      <div className="space-y-6">
        <Skeleton variant="title" width="40%" height="2.5rem" />
        <div className="grid gap-4 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} variant="block" height="9rem" />
          ))}
        </div>
      </div>
    )
  }

  const enrichedPct = data.total_lessons ? data.enriched_lessons / data.total_lessons : 0
  const anyAvailable = data.drills.some((d) => d.available)

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Practice"
        title={data.course_title}
        description="Drills built from this course's own content. Each one exercises a different way of learning."
        backTo="/practice"
        backLabel="All practice"
      />

      {/* Drills come from enriched lessons, so the user can see exactly why
          something is locked and what unlocks it. */}
      <Card padding="lg">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-callout text-fg font-medium">Lesson content generated</p>
            <p className="text-caption text-fg-subtle mt-0.5 tabular-nums">
              {data.enriched_lessons} of {data.total_lessons} lessons
              {!anyAvailable && ' — open a lesson to unlock drills'}
            </p>
          </div>
          <ButtonLink to={`/courses/${courseId}`} variant="secondary" size="sm">
            Go to lessons
          </ButtonLink>
        </div>
        <ProgressBar
          value={enrichedPct}
          size="sm"
          tone={anyAvailable ? 'success' : 'neutral'}
          label="Lessons with generated content"
          hideLabel
          className="mt-4"
        />
      </Card>

      <motion.ul
        variants={listContainer}
        initial="hidden"
        animate="show"
        className="grid gap-4 sm:grid-cols-2"
      >
        {data.drills.map((drill) => {
          const { icon, tone } = DRILL_VISUALS[drill.kind]
          const body = (
            <>
              <div className="mb-3 flex items-start justify-between gap-3">
                <IconBadge icon={drill.available ? icon : Lock} tone={drill.available ? tone : 'neutral'} />
                <Badge tone={drill.available ? tone : 'neutral'} size="sm">
                  {drill.modality}
                </Badge>
              </div>
              <h2 className="text-headline text-fg">{drill.title}</h2>
              <p className="text-caption text-fg-muted mt-1.5">{drill.description}</p>
              {drill.available ? (
                <p className="text-caption text-brand-300 mt-3 inline-flex items-center gap-1.5">
                  <Play size={12} aria-hidden="true" />
                  {drill.item_count} item{drill.item_count === 1 ? '' : 's'} ready
                </p>
              ) : (
                <p className="text-caption text-fg-faint mt-3">{drill.reason}</p>
              )}
            </>
          )

          return (
            <motion.li key={drill.kind} variants={listItem}>
              {drill.available ? (
                <Card interactive padding="none" className="h-full">
                  <Link to={`/practice/${courseId}/${drill.kind}`} className="block h-full p-4">
                    {body}
                  </Link>
                </Card>
              ) : (
                <Card
                  padding="md"
                  className={cn('h-full opacity-60')}
                  aria-disabled="true"
                >
                  {body}
                </Card>
              )}
            </motion.li>
          )
        })}
      </motion.ul>
    </div>
  )
}
