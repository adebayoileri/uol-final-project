import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { CalendarCheck, Flame, Layers, Play, RotateCcw, SlidersHorizontal, X } from 'lucide-react'
import {
  getReviewCourses,
  reviewFilterParams,
  type ReviewCourseGroup,
  type ReviewFilters,
} from '../api'
import {
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  PageHeader,
  ProgressBar,
  Skeleton,
  StatTile,
} from '../components/ui'
import { listContainer, listItem } from '../motion/springs'

const EMPTY: ReviewFilters = {}

export default function ReviewHub() {
  const navigate = useNavigate()
  const [groups, setGroups] = useState<ReviewCourseGroup[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<ReviewFilters>(EMPTY)
  const [showFilters, setShowFilters] = useState(false)

  const load = useCallback(() => {
    setGroups(null)
    setError(null)
    getReviewCourses(filters)
      .then(setGroups)
      .catch((err: Error) => setError(err.message))
  }, [filters])

  useEffect(load, [load])

  const activeFilterCount = Object.values(filters).filter(Boolean).length

  const totals = useMemo(() => {
    const rows = groups ?? []
    return {
      due: rows.reduce((s, g) => s + g.due_now, 0),
      cards: rows.reduce((s, g) => s + g.total_cards, 0),
      courses: rows.filter((g) => g.due_now > 0).length,
    }
  }, [groups])

  function startSession(courseId?: string) {
    const qs = reviewFilterParams(filters).toString()
    const path = courseId ? `/courses/${courseId}/review` : '/review/session'
    navigate(qs ? `${path}?${qs}` : path)
  }

  function setFilter(key: keyof ReviewFilters, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value || undefined }))
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Review"
        description="Pick a course to review, or work through everything that's due."
        actions={
          <Button
            variant={activeFilterCount > 0 ? 'secondary' : 'ghost'}
            icon={SlidersHorizontal}
            onClick={() => setShowFilters((o) => !o)}
          >
            Filters
            {activeFilterCount > 0 && (
              <span className="bg-brand-500 text-eyebrow ml-1.5 rounded-full px-1.5 py-0.5 text-on-brand tabular-nums">
                {activeFilterCount}
              </span>
            )}
          </Button>
        }
      />

      {showFilters && (
        <Card padding="lg">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Added after" hint="When the card was created">
              {(p) => (
                <Input
                  type="date"
                  value={filters.created_from ?? ''}
                  onChange={(e) => setFilter('created_from', e.target.value)}
                  {...p}
                />
              )}
            </Field>
            <Field label="Added before">
              {(p) => (
                <Input
                  type="date"
                  value={filters.created_to ?? ''}
                  onChange={(e) => setFilter('created_to', e.target.value)}
                  {...p}
                />
              )}
            </Field>
            <Field label="Due after" hint="When the card next comes up">
              {(p) => (
                <Input
                  type="date"
                  value={filters.due_from ?? ''}
                  onChange={(e) => setFilter('due_from', e.target.value)}
                  {...p}
                />
              )}
            </Field>
            <Field label="Due before">
              {(p) => (
                <Input
                  type="date"
                  value={filters.due_to ?? ''}
                  onChange={(e) => setFilter('due_to', e.target.value)}
                  {...p}
                />
              )}
            </Field>
          </div>
          {activeFilterCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              icon={X}
              onClick={() => setFilters(EMPTY)}
              className="mt-4"
            >
              Clear filters
            </Button>
          )}
        </Card>
      )}

      {error ? (
        <ErrorState message={error} onRetry={load} backTo="/courses" backLabel="Go to library" />
      ) : groups === null ? (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Card key={i} padding="lg">
                <Skeleton variant="title" width="40%" />
              </Card>
            ))}
          </div>
          {[0, 1, 2].map((i) => (
            <Card key={i} padding="lg">
              <Skeleton variant="title" width="35%" />
              <Skeleton width="60%" className="mt-3" />
            </Card>
          ))}
        </div>
      ) : groups.length === 0 ? (
        <Card padding="none">
          <EmptyState
            icon={CalendarCheck}
            title={activeFilterCount > 0 ? 'Nothing matches those filters' : 'Nothing to review yet'}
            description={
              activeFilterCount > 0
                ? 'Try widening the date range, or clear the filters to see everything.'
                : 'Generate questions on a lesson and they become review cards automatically.'
            }
            action={
              activeFilterCount > 0 ? (
                <Button icon={X} onClick={() => setFilters(EMPTY)}>
                  Clear filters
                </Button>
              ) : (
                <ButtonLink to="/courses">Go to library</ButtonLink>
              )
            }
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatTile icon={Flame} label="Cards due now" value={totals.due} tone={totals.due > 0 ? 'warn' : 'neutral'} countUp />
            <StatTile icon={Layers} label="Courses waiting" value={totals.courses} countUp />
            <StatTile icon={RotateCcw} label="Cards in total" value={totals.cards} tone="info" countUp />
          </div>

          {totals.due > 0 && (
            <Card padding="lg" elevation={2} className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-headline text-fg">Review everything due</p>
                <p className="text-caption text-fg-subtle mt-0.5">
                  {totals.due} card{totals.due === 1 ? '' : 's'} across {totals.courses} course
                  {totals.courses === 1 ? '' : 's'}, oldest first
                </p>
              </div>
              <Button size="lg" icon={Play} onClick={() => startSession()}>
                Start mixed session
              </Button>
            </Card>
          )}

          <motion.ul variants={listContainer} initial="hidden" animate="show" className="space-y-3">
            {groups.map((g) => {
              const ready = g.due_now > 0
              const pct = g.total_cards ? g.due_now / g.total_cards : 0
              return (
                <motion.li key={g.course_id} variants={listItem}>
                  <Card padding="lg" className={ready ? undefined : 'opacity-60'}>
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <h2 className="text-headline text-fg truncate">{g.title}</h2>
                          <Badge tone="brand" size="sm">
                            {g.category}
                          </Badge>
                        </div>
                        <p className="text-caption text-fg-subtle mt-1 tabular-nums">
                          {ready ? (
                            <>
                              {g.due_now} of {g.total_cards} card
                              {g.total_cards === 1 ? '' : 's'} due
                            </>
                          ) : (
                            <>Nothing due — {g.total_cards} card{g.total_cards === 1 ? '' : 's'} scheduled ahead</>
                          )}
                        </p>
                        <ProgressBar
                          value={pct}
                          size="xs"
                          tone={ready ? 'warn' : 'neutral'}
                          label={`${g.title} cards due`}
                          hideLabel
                          className="mt-3 max-w-md"
                        />
                      </div>
                      <Button
                        icon={Play}
                        onClick={() => startSession(g.course_id)}
                        disabled={!ready}
                        variant={ready ? 'primary' : 'secondary'}
                      >
                        {ready ? 'Review' : 'Nothing due'}
                      </Button>
                    </div>
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
