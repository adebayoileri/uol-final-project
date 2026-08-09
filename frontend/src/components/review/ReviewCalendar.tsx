import { useEffect, useState } from 'react'
import { CalendarDays } from 'lucide-react'
import { getReviewForecast, type ForecastDay, type ReviewQueueResponse } from '../../api'
import { Card, Skeleton } from '../ui'
import { cn } from '../../lib/cn'

const DAY_LABELS = ['S', 'M', 'T', 'W', 'T', 'F', 'S']

/** Tint by load. Never invents a value: 0 stays visibly empty. */
function cellTone(count: number, max: number) {
  if (count === 0) return 'bg-surface-raised text-fg-faint'
  const ratio = max > 0 ? count / max : 0
  if (ratio > 0.66) return 'bg-brand-500 text-white'
  if (ratio > 0.33) return 'bg-brand-700 text-brand-50'
  return 'bg-brand-900 text-brand-200'
}

interface ReviewCalendarProps {
  courseId?: string
  queue: ReviewQueueResponse | null
}

export default function ReviewCalendar({ courseId, queue }: ReviewCalendarProps) {
  const [forecast, setForecast] = useState<ForecastDay[] | null>(null)
  // The endpoint is optional: an older backend 404s and we degrade to the
  // three queue buckets rather than fabricating per-day counts.
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    let cancelled = false
    getReviewForecast(courseId, 28)
      .then((f) => !cancelled && setForecast(f))
      .catch(() => !cancelled && setUnavailable(true))
    return () => {
      cancelled = true
    }
  }, [courseId])

  const max = forecast ? Math.max(...forecast.map((d) => d.count), 0) : 0
  const todayDow = new Date().getDay()

  return (
    <Card padding="none">
      <div className="border-hairline flex items-center gap-2 border-b px-4 py-3">
        <CalendarDays size={14} className="text-brand-300" aria-hidden="true" />
        <h2 className="text-callout text-fg font-medium">Review schedule</h2>
      </div>

      {!unavailable && (
        <div className="p-4">
          {forecast === null ? (
            <Skeleton variant="block" height="7rem" />
          ) : (
            <>
              <div className="text-eyebrow text-fg-faint mb-2 grid grid-cols-7 gap-1 text-center">
                {Array.from({ length: 7 }).map((_, i) => (
                  <span key={i}>{DAY_LABELS[(todayDow + i) % 7]}</span>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-1">
                {forecast.map((day, i) => {
                  const d = new Date(day.date)
                  return (
                    <div
                      key={day.date}
                      title={`${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} — ${day.count} card${day.count === 1 ? '' : 's'}`}
                      className={cn(
                        'text-eyebrow grid aspect-square place-items-center rounded-sm tabular-nums',
                        cellTone(day.count, max),
                        i === 0 && 'ring-brand-300 ring-1',
                      )}
                    >
                      {day.count > 0 ? day.count : d.getDate()}
                    </div>
                  )
                })}
              </div>
              <p className="text-caption text-fg-faint mt-3">
                Next 28 days. Overdue cards are shown on today.
              </p>
            </>
          )}
        </div>
      )}

      {queue && (
        <dl className="divide-hairline border-hairline divide-y border-t">
          {[
            ['Due now', queue.due_now],
            ['Due today', queue.due_today],
            ['Due this week', queue.due_this_week],
            ['Total cards', queue.total],
          ].map(([label, value]) => (
            <div key={label as string} className="flex items-center justify-between px-4 py-2.5">
              <dt className="text-caption text-fg-subtle">{label}</dt>
              <dd className="text-callout text-fg tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </Card>
  )
}
