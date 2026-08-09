import { useCallback, useEffect, useState } from 'react'
import { CalendarClock, Clock, Sparkles, Target } from 'lucide-react'
import { getInsights, type InsightsResponse } from '../api'
import { Card, ErrorState, IconBadge, ProgressBar, Skeleton } from './ui'

function fmtHour(h: number) {
  const period = h < 12 ? 'am' : 'pm'
  const display = h === 0 ? 12 : h > 12 ? h - 12 : h
  return `${display}${period}`
}

function fmtDue(iso: string) {
  try {
    const d = new Date(iso)
    const diff = d.getTime() - Date.now()
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24))
    if (days <= 0) return 'now'
    if (days === 1) return 'tomorrow'
    return `in ${days}d`
  } catch {
    return iso
  }
}

interface InsightsPanelProps {
  courseId: string
}

/**
 * Every row is backed by a real endpoint value. Loading, failure and
 * genuinely-empty are three distinct states — the panel used to render null for
 * all three, so a broken endpoint looked identical to "no data yet".
 */
export default function InsightsPanel({ courseId }: InsightsPanelProps) {
  const [data, setData] = useState<InsightsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getInsights(courseId)
      .then((d) => !cancelled && setData(d))
      .catch((err: Error) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [courseId])

  useEffect(load, [load])

  return (
    <Card padding="none">
      <div className="border-hairline flex items-center gap-2 border-b px-4 py-3">
        <Sparkles size={14} className="text-brand-300" aria-hidden="true" />
        <h2 className="text-callout text-fg font-medium">Learning insights</h2>
      </div>

      <div className="divide-hairline divide-y">
        {loading ? (
          <div className="space-y-3 p-4">
            <Skeleton lines={2} />
            <Skeleton lines={2} />
          </div>
        ) : error ? (
          <div className="p-4">
            <ErrorState inline message={error} onRetry={load} />
          </div>
        ) : !data ? null : (
          <>
            <Row
              icon={Clock}
              tone="info"
              label="Optimal study time"
              value={
                data.optimal_study_time
                  ? `${fmtHour(data.optimal_study_time.start_hour)}–${fmtHour(data.optimal_study_time.end_hour)}`
                  : 'Learning…'
              }
              hint={
                data.optimal_study_time
                  ? 'When your answers score highest'
                  : 'Needs ~20 answered questions'
              }
            />

            {data.recommended_focus && (
              <div className="p-4">
                <div className="flex items-start gap-3">
                  <IconBadge icon={Target} tone="warn" size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="text-caption text-fg-subtle">Recommended focus</p>
                    <p className="text-callout text-fg mt-0.5 line-clamp-2">
                      {data.recommended_focus.concept}
                    </p>
                    <ProgressBar
                      value={data.recommended_focus.mastery}
                      size="xs"
                      tone="warn"
                      className="mt-2"
                    />
                    <p className="text-caption text-fg-faint mt-2">
                      {data.recommended_focus.rationale}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {data.next_reviews.length > 0 && (
              <div className="p-4">
                <div className="flex items-start gap-3">
                  <IconBadge icon={CalendarClock} tone="brand" size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="text-caption text-fg-subtle mb-2">Upcoming reviews</p>
                    <ul className="space-y-1.5">
                      {data.next_reviews.map((r, i) => (
                        <li key={i} className="flex items-baseline justify-between gap-2">
                          <span className="text-caption text-fg-muted truncate">
                            {r.question_text}
                          </span>
                          <span className="text-caption text-fg-faint shrink-0 tabular-nums">
                            {fmtDue(r.due)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {!data.optimal_study_time &&
              !data.recommended_focus &&
              data.next_reviews.length === 0 && (
                <p className="text-caption text-fg-subtle p-4">
                  Study a few lessons and answer some questions — insights appear once there's
                  enough history.
                </p>
              )}
          </>
        )}
      </div>
    </Card>
  )
}

function Row({
  icon,
  tone,
  label,
  value,
  hint,
}: {
  icon: typeof Clock
  tone: 'brand' | 'info' | 'warn'
  label: string
  value: string
  hint?: string
}) {
  return (
    <div className="flex items-start gap-3 p-4">
      <IconBadge icon={icon} tone={tone} size="sm" />
      <div className="min-w-0 flex-1">
        <p className="text-caption text-fg-subtle">{label}</p>
        <p className="text-callout text-fg mt-0.5">{value}</p>
        {hint && <p className="text-caption text-fg-faint mt-0.5">{hint}</p>}
      </div>
    </div>
  )
}
