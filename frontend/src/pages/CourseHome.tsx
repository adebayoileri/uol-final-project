import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import {
  Brain,
  CheckCircle2,
  ChevronDown,
  Circle,
  Clock,
  Flame,
  GraduationCap,
  PlayCircle,
  RotateCcw,
  Route as RouteIcon,
} from 'lucide-react'
import { getCourse, getReviewQueue, type CourseResponse, type ReviewQueueResponse } from '../api'
import InsightsPanel from '../components/InsightsPanel'
import SearchPanel from '../components/SearchPanel'
import {
  Badge,
  ButtonLink,
  Card,
  DashboardSkeleton,
  ErrorState,
  PageHeader,
  ProgressBar,
  StatTile,
} from '../components/ui'
import { listContainer, listItem, springSheet } from '../motion/springs'

export default function CourseHome() {
  const { courseId } = useParams<{ courseId: string }>()
  const [course, setCourse] = useState<CourseResponse | null>(null)
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [openModules, setOpenModules] = useState<Set<string>>(new Set())

  const load = useCallback(() => {
    if (!courseId) return
    setLoading(true)
    setError(null)
    Promise.all([getCourse(courseId), getReviewQueue(courseId)])
      .then(([c, q]) => {
        setCourse(c)
        setQueue(q)
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [courseId])

  useEffect(load, [load])

  const stats = useMemo(() => {
    if (!course) return null
    let total = 0
    let done = 0
    let remainingMinutes = 0
    let nextLesson: { id: string; title: string; moduleId: string } | null = null
    for (const mod of course.modules) {
      for (const lesson of mod.lessons) {
        total += 1
        if (lesson.completed_at) {
          done += 1
        } else {
          remainingMinutes += lesson.duration_minutes || 0
          if (!nextLesson) nextLesson = { id: lesson.id, title: lesson.title, moduleId: mod.id }
        }
      }
    }
    return { total, done, remainingMinutes, nextLesson, pct: total ? done / total : 0 }
  }, [course])

  // Open the module holding the next lesson, so the useful thing is visible.
  useEffect(() => {
    if (stats?.nextLesson) setOpenModules(new Set([stats.nextLesson.moduleId]))
  }, [stats?.nextLesson])

  if (!courseId) {
    return <ErrorState message="No course selected." backTo="/courses" backLabel="Go to library" />
  }
  if (error) {
    return <ErrorState message={error} onRetry={load} backTo="/courses" backLabel="Go to library" />
  }
  if (loading) return <DashboardSkeleton tiles={4} />
  if (!course || !stats) return null

  const dueNow = queue?.due_now ?? 0
  const allDone = stats.total > 0 && stats.done === stats.total

  function toggleModule(id: string) {
    setOpenModules((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={course.category}
        title={course.title}
        description={course.description}
        backTo="/courses"
        backLabel="Library"
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_20rem]">
        <div className="space-y-6">
          {/* Course-level progress — the course page previously had none. */}
          <Card padding="lg" elevation={2}>
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-title-lg text-fg tabular-nums">
                  {Math.round(stats.pct * 100)}
                  <span className="text-headline text-fg-subtle">%</span>
                </p>
                <p className="text-caption text-fg-subtle mt-0.5">
                  {stats.done} of {stats.total} lessons
                  {!allDone && stats.remainingMinutes > 0 && (
                    <> · ~{stats.remainingMinutes}m left</>
                  )}
                </p>
              </div>
              {allDone && (
                <Badge tone="success" icon={CheckCircle2}>
                  Course complete
                </Badge>
              )}
            </div>
            <ProgressBar
              value={stats.pct}
              size="md"
              tone={allDone ? 'success' : 'brand'}
              label="Course progress"
              hideLabel
              className="mt-4"
            />

            <div className="mt-5 flex flex-wrap gap-2">
              {stats.nextLesson ? (
                <ButtonLink
                  to={`/courses/${courseId}/lessons/${stats.nextLesson.id}`}
                  size="lg"
                  icon={PlayCircle}
                >
                  Continue
                </ButtonLink>
              ) : (
                <ButtonLink to={`/courses/${courseId}/complete`} size="lg" icon={GraduationCap}>
                  See your results
                </ButtonLink>
              )}
              {dueNow > 0 && (
                <ButtonLink
                  to={`/courses/${courseId}/review`}
                  variant="secondary"
                  size="lg"
                  icon={RotateCcw}
                >
                  Review {dueNow} card{dueNow === 1 ? '' : 's'}
                </ButtonLink>
              )}
              <ButtonLink
                to={`/courses/${courseId}/timeline`}
                variant="ghost"
                size="lg"
                icon={RouteIcon}
              >
                Timeline
              </ButtonLink>
            </div>
            {stats.nextLesson && (
              <p className="text-caption text-fg-subtle mt-3 truncate">
                Next up: {stats.nextLesson.title}
              </p>
            )}
          </Card>

          {/* Modules */}
          <motion.div
            variants={listContainer}
            initial="hidden"
            animate="show"
            className="space-y-3"
          >
            {course.modules.map((mod, mi) => {
              const modDone = mod.lessons.filter((l) => l.completed_at).length
              const modPct = mod.lessons.length ? modDone / mod.lessons.length : 0
              const isOpen = openModules.has(mod.id)
              return (
                <motion.section key={mod.id} variants={listItem}>
                  <Card padding="none" className="overflow-hidden">
                    <button
                      onClick={() => toggleModule(mod.id)}
                      aria-expanded={isOpen}
                      className="hover:bg-surface-raised flex w-full items-center gap-4 px-5 py-4 text-left transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-eyebrow text-fg-subtle uppercase">Module {mi + 1}</p>
                        <h2 className="text-headline text-fg mt-0.5">{mod.title}</h2>
                        <div className="mt-2.5 flex items-center gap-3">
                          <ProgressBar
                            value={modPct}
                            size="xs"
                            tone={modPct === 1 ? 'success' : 'brand'}
                            className="max-w-40"
                          />
                          <span className="text-caption text-fg-subtle shrink-0 tabular-nums">
                            {modDone}/{mod.lessons.length}
                          </span>
                        </div>
                      </div>
                      <ChevronDown
                        size={18}
                        className={`text-fg-faint shrink-0 transition-transform duration-[--duration-base] ${
                          isOpen ? 'rotate-180' : ''
                        }`}
                        aria-hidden="true"
                      />
                    </button>

                    <AnimatePresence initial={false}>
                      {isOpen && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1, transition: springSheet }}
                          exit={{ height: 0, opacity: 0, transition: { duration: 0.15 } }}
                          className="overflow-hidden"
                        >
                          <ul className="divide-hairline border-hairline divide-y border-t">
                            {mod.lessons.map((lesson) => {
                              const isNext = stats.nextLesson?.id === lesson.id
                              const Icon = lesson.completed_at
                                ? CheckCircle2
                                : isNext
                                  ? PlayCircle
                                  : Circle
                              return (
                                <li key={lesson.id}>
                                  <motion.div whileHover={{ x: 2 }}>
                                    <Link
                                      to={`/courses/${courseId}/lessons/${lesson.id}`}
                                      className="hover:bg-surface-raised flex items-center gap-3 px-5 py-3 transition-colors"
                                    >
                                      <Icon
                                        size={17}
                                        className={
                                          lesson.completed_at
                                            ? 'text-success shrink-0'
                                            : isNext
                                              ? 'text-brand-400 shrink-0'
                                              : 'text-fg-faint shrink-0'
                                        }
                                        aria-hidden="true"
                                      />
                                      <span
                                        className={`text-body flex-1 ${
                                          lesson.completed_at ? 'text-fg-subtle' : 'text-fg'
                                        }`}
                                      >
                                        {lesson.title}
                                      </span>
                                      {isNext && (
                                        <Badge tone="brand" size="sm">
                                          Next
                                        </Badge>
                                      )}
                                      <span className="text-caption text-fg-faint shrink-0 tabular-nums">
                                        {lesson.duration_minutes}m
                                      </span>
                                    </Link>
                                  </motion.div>
                                </li>
                              )
                            })}
                          </ul>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </Card>
                </motion.section>
              )
            })}
          </motion.div>
        </div>

        {/* Sidebar */}
        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <div className="grid grid-cols-2 gap-3">
            <StatTile icon={GraduationCap} label="Lessons done" value={stats.done} countUp />
            <StatTile
              icon={Flame}
              label="Cards due"
              value={dueNow}
              tone={dueNow > 0 ? 'warn' : 'neutral'}
              countUp
            />
            <StatTile icon={Brain} label="Total cards" value={queue?.total ?? 0} tone="info" countUp />
            <StatTile
              icon={Clock}
              label="Minutes left"
              value={stats.remainingMinutes}
              tone="neutral"
              countUp
            />
          </div>

          <InsightsPanel courseId={courseId} />

          <SearchPanel courseId={courseId} />
        </aside>
      </div>
    </div>
  )
}
