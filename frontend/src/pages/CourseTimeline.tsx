import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { motion, useInView } from 'motion/react'
import { Check, Clock, Flame, Play, Target } from 'lucide-react'
import { getTimeline, type TimelineLesson, type TimelineResponse } from '../api'
import {
  Card,
  DashboardSkeleton,
  ErrorState,
  PageHeader,
  ProgressBar,
  StatTile,
} from '../components/ui'
import { springDefault } from '../motion/springs'
import { cn } from '../lib/cn'

type NodeStatus = 'done' | 'current' | 'upcoming'

function TimelineNode({
  lesson,
  status,
  isLast,
  onOpen,
  index,
}: {
  lesson: TimelineLesson
  status: NodeStatus
  isLast: boolean
  onOpen: () => void
  index: number
}) {
  const ref = useRef<HTMLLIElement>(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })

  return (
    <li ref={ref} className="flex gap-4">
      <div className="flex flex-col items-center">
        <motion.span
          initial={{ scale: 0.5, opacity: 0 }}
          animate={inView ? { scale: 1, opacity: 1 } : undefined}
          transition={{ ...springDefault, delay: (index % 6) * 0.06 }}
          className={cn(
            'grid size-6 shrink-0 place-items-center rounded-full border-2',
            status === 'done' && 'bg-success border-success text-canvas',
            status === 'current' && 'border-brand-400 bg-brand-500/20 text-brand-300',
            status === 'upcoming' && 'border-border bg-surface text-transparent',
          )}
        >
          {status === 'done' && <Check size={13} strokeWidth={3} aria-hidden="true" />}
          {status === 'current' && <Play size={11} fill="currentColor" aria-hidden="true" />}
        </motion.span>
        {!isLast && (
          <motion.span
            initial={{ scaleY: 0 }}
            animate={inView ? { scaleY: 1 } : undefined}
            transition={{ ...springDefault, delay: (index % 6) * 0.06 + 0.05 }}
            className="bg-hairline my-1 w-px flex-1 origin-top"
          />
        )}
      </div>

      <div className="min-w-0 flex-1 pb-4">
        <motion.button
          onClick={onOpen}
          whileHover={{ x: 2 }}
          transition={springDefault}
          className={cn(
            'border-border bg-surface hover:border-border-strong hover:bg-surface-raised w-full rounded-md border px-4 py-3 text-left transition-colors',
            status === 'current' && 'border-brand-500/40',
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <span className={cn('text-body', status === 'done' ? 'text-fg-subtle' : 'text-fg')}>
              {lesson.title}
            </span>
            <span className="text-caption text-fg-faint shrink-0 tabular-nums">
              {lesson.duration_minutes}m
            </span>
          </div>
          {lesson.completed_at && (
            <span className="text-caption text-success mt-1 block">
              Completed {new Date(lesson.completed_at).toLocaleDateString()}
            </span>
          )}
        </motion.button>
      </div>
    </li>
  )
}

export default function CourseTimeline() {
  const { courseId } = useParams<{ courseId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<TimelineResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (!courseId) return
    setLoading(true)
    setError(null)
    getTimeline(courseId)
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [courseId])

  useEffect(load, [load])

  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={load}
        backTo={`/courses/${courseId}`}
        backLabel="Back to course"
      />
    )
  }
  if (loading) return <DashboardSkeleton tiles={3} />
  if (!data) return null

  const allLessons = data.modules.flatMap((m) => m.lessons)
  const total = allLessons.length
  const completed = allLessons.filter((l) => l.completed_at).length
  const pct = total ? completed / total : 0
  const remainingMins = data.total_minutes - data.completed_minutes
  const currentId = allLessons.find((l) => !l.completed_at)?.id ?? null

  let flatIndex = 0

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Learning plan"
        title="Timeline"
        description="Every lesson in order, with what's done and what's left."
        backTo={`/courses/${courseId}`}
        backLabel="Back to course"
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_18rem]">
        <div className="space-y-8">
          {data.modules.map((module, mi) => (
            <section key={`${module.title}-${mi}`}>
              <div className="mb-4">
                <p className="text-eyebrow text-fg-subtle uppercase">Module {mi + 1}</p>
                <h2 className="text-headline text-fg mt-0.5">{module.title}</h2>
              </div>
              <ul>
                {module.lessons.map((lesson, li) => {
                  const status: NodeStatus = lesson.completed_at
                    ? 'done'
                    : lesson.id === currentId
                      ? 'current'
                      : 'upcoming'
                  const node = (
                    <TimelineNode
                      key={lesson.id}
                      lesson={lesson}
                      status={status}
                      index={flatIndex}
                      isLast={li === module.lessons.length - 1}
                      onOpen={() => navigate(`/courses/${courseId}/lessons/${lesson.id}`)}
                    />
                  )
                  flatIndex += 1
                  return node
                })}
              </ul>
            </section>
          ))}
        </div>

        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <Card padding="lg">
            <p className="text-title-lg text-fg tabular-nums">
              {Math.round(pct * 100)}
              <span className="text-headline text-fg-subtle">%</span>
            </p>
            <p className="text-caption text-fg-subtle mt-0.5">
              {completed} of {total} lessons
            </p>
            <ProgressBar
              value={pct}
              size="md"
              label="Overall progress"
              hideLabel
              className="mt-4"
            />
          </Card>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-1">
            <StatTile
              icon={Clock}
              label="Time remaining"
              value={remainingMins}
              unit="m"
              tone="info"
              countUp
            />
            <StatTile
              icon={Flame}
              label="Day streak"
              value={data.streak}
              tone={data.streak > 0 ? 'warn' : 'neutral'}
              countUp
            />
            <StatTile
              icon={Target}
              label="Time invested"
              value={data.completed_minutes}
              unit="m"
              tone="success"
              countUp
              className="col-span-2 lg:col-span-1"
            />
          </div>
        </aside>
      </div>
    </div>
  )
}
