import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import { BookOpen, ChevronRight, Dumbbell } from 'lucide-react'
import { getCourseDrills, getCourses, type CourseDrills, type CourseSummaryResponse } from '../api'
import {
  Badge,
  ButtonLink,
  Card,
  CardListSkeleton,
  EmptyState,
  ErrorState,
  PageHeader,
} from '../components/ui'
import { listContainer, listItem } from '../motion/springs'

interface Row {
  course: CourseSummaryResponse
  drills: CourseDrills | null
}

export default function PracticeHub() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setRows(null)
    setError(null)
    getCourses()
      .then(async (courses) => {
        // Availability is per course; fetched in parallel so the page isn't
        // gated on the slowest one.
        const drills = await Promise.all(
          courses.map((c) => getCourseDrills(c.id).catch(() => null)),
        )
        setRows(courses.map((course, i) => ({ course, drills: drills[i] })))
      })
      .catch((err: Error) => setError(err.message))
  }, [])

  useEffect(load, [load])

  return (
    <div className="space-y-8">
      <PageHeader
        title="Practice"
        description="Drills built from your own course content — multiple choice, matching, step ordering, listening and pronunciation."
      />

      {error ? (
        <ErrorState message={error} onRetry={load} backTo="/courses" backLabel="Go to library" />
      ) : rows === null ? (
        <CardListSkeleton count={4} />
      ) : rows.length === 0 ? (
        <Card padding="none">
          <EmptyState
            icon={BookOpen}
            title="No courses yet"
            description="Practice drills are generated from your lessons, so start a course first."
            action={<ButtonLink to="/">Create a course</ButtonLink>}
          />
        </Card>
      ) : (
        <motion.ul
          variants={listContainer}
          initial="hidden"
          animate="show"
          className="grid gap-4 sm:grid-cols-2"
        >
          {rows.map(({ course, drills }) => {
            const available = drills?.drills.filter((d) => d.available) ?? []
            const ready = available.length > 0
            return (
              <motion.li key={course.id} variants={listItem}>
                <Card interactive padding="none" className="h-full">
                  <Link to={`/practice/${course.id}`} className="group flex h-full flex-col p-4">
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

                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      {ready ? (
                        available.map((d) => (
                          <Badge key={d.kind} tone="success" size="sm">
                            {d.title}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-caption text-fg-subtle inline-flex items-center gap-1.5">
                          <Dumbbell size={13} aria-hidden="true" />
                          {drills
                            ? `No drills yet — ${drills.enriched_lessons} of ${drills.total_lessons} lessons generated`
                            : 'Drills unavailable'}
                        </span>
                      )}
                    </div>
                  </Link>
                </Card>
              </motion.li>
            )
          })}
        </motion.ul>
      )}
    </div>
  )
}
