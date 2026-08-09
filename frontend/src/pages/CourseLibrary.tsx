import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import { BookOpen, ChevronRight, Flame, GraduationCap, Layers } from 'lucide-react'
import { getCourses, type CourseSummaryResponse } from '../api'
import SearchPanel from '../components/SearchPanel'
import {
  Badge,
  ButtonLink,
  Card,
  CardListSkeleton,
  EmptyState,
  ErrorState,
  PageHeader,
  ProgressBar,
  Skeleton,
  StatTile,
} from '../components/ui'
import { listContainer, listItem } from '../motion/springs'

export default function CourseLibrary() {
  const [courses, setCourses] = useState<CourseSummaryResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    getCourses()
      .then(setCourses)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  // Aggregated from data already on the list response — no extra endpoint.
  const totals = courses.reduce(
    (acc, c) => ({
      lessons: acc.lessons + c.progress_summary.total_lessons,
      completed: acc.completed + c.progress_summary.completed_lessons,
      due: acc.due + c.progress_summary.due_now,
    }),
    { lessons: 0, completed: 0, due: 0 },
  )

  return (
    <div className="space-y-8">
      <PageHeader
        title="Library"
        description="Everything you've generated, with progress and what's due."
      />

      {error ? (
        <ErrorState message={error} onRetry={load} backTo="/" backLabel="Start a course" />
      ) : loading ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Card key={i} padding="lg">
                <Skeleton variant="circle" width="2.25rem" className="mb-3" />
                <Skeleton variant="title" width="40%" />
                <Skeleton width="60%" className="mt-2" />
              </Card>
            ))}
          </div>
          <CardListSkeleton count={6} />
        </>
      ) : courses.length === 0 ? (
        <Card padding="none">
          <EmptyState
            icon={BookOpen}
            title="No courses yet"
            description="Describe a goal and a full course is generated for you — modules, lessons, questions and a review schedule."
            action={<ButtonLink to="/">Create your first course</ButtonLink>}
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatTile icon={Layers} label="Courses" value={courses.length} countUp />
            <StatTile
              icon={GraduationCap}
              label="Lessons completed"
              value={totals.completed}
              tone="success"
              countUp
              hint={`of ${totals.lessons}`}
            />
            <StatTile
              icon={Flame}
              label="Cards due now"
              value={totals.due}
              tone={totals.due > 0 ? 'warn' : 'neutral'}
              countUp
            />
          </div>

          <SearchPanel />

          <motion.ul
            variants={listContainer}
            initial="hidden"
            animate="show"
            className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
          >
            {courses.map((course) => {
              const { total_lessons, completed_lessons, due_now } = course.progress_summary
              const pct = total_lessons ? completed_lessons / total_lessons : 0
              const done = total_lessons > 0 && completed_lessons === total_lessons
              return (
                <motion.li key={course.id} variants={listItem}>
                  <Card interactive padding="none" className="h-full">
                    <Link to={`/courses/${course.id}`} className="group flex h-full flex-col p-4">
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <Badge tone="brand" size="sm">
                          {course.category}
                        </Badge>
                        <ChevronRight
                          size={16}
                          className="text-fg-faint shrink-0 transition-transform duration-[--duration-fast] group-hover:translate-x-0.5"
                          aria-hidden="true"
                        />
                      </div>

                      <h2 className="text-headline text-fg line-clamp-2 flex-1">{course.title}</h2>

                      <div className="mt-4 space-y-2">
                        <ProgressBar value={pct} size="xs" tone={done ? 'success' : 'brand'} />
                        <div className="text-caption text-fg-subtle flex items-center justify-between gap-2">
                          <span className="tabular-nums">
                            {completed_lessons}/{total_lessons} lessons
                          </span>
                          {done ? (
                            <Badge tone="success" size="sm">
                              Complete
                            </Badge>
                          ) : (
                            due_now > 0 && (
                              <Badge tone="warn" size="sm" icon={Flame}>
                                {due_now} due
                              </Badge>
                            )
                          )}
                        </div>
                      </div>
                    </Link>
                  </Card>
                </motion.li>
              )
            })}
          </motion.ul>
        </>
      )}
    </div>
  )
}
