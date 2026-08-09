import { useEffect, useState } from 'react'
import { getInsights, type InsightsResponse } from '../api'

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
    if (days <= 0) return 'due now'
    if (days === 1) return 'due tomorrow'
    return `due in ${days} days`
  } catch {
    return iso
  }
}

interface InsightsPanelProps {
  courseId: string
}

export default function InsightsPanel({ courseId }: InsightsPanelProps) {
  const [data, setData] = useState<InsightsResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getInsights(courseId)
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch(() => {
        if (!cancelled) setData(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [courseId])

  if (loading) return null
  if (!data) return null

  const { optimal_study_time, recommended_focus, next_reviews } = data
  const hasAny = optimal_study_time || recommended_focus || (next_reviews && next_reviews.length > 0)
  if (!hasAny) return null

  return (
    <section className="space-y-3">
      <h3 className="text-xs text-gray-500 uppercase tracking-wider">Learning insights</h3>

      {optimal_study_time && (
        <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-3">
          <p className="text-xs text-violet-400 font-medium mb-0.5">Optimal study time</p>
          <p className="text-sm text-white">
            {fmtHour(optimal_study_time.start_hour)} – {fmtHour(optimal_study_time.end_hour)}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">Based on your answer accuracy patterns</p>
        </div>
      )}

      {!optimal_study_time && (
        <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-3">
          <p className="text-xs text-gray-500">
            Learning your patterns… answer more questions to unlock study time insights.
          </p>
        </div>
      )}

      {recommended_focus && (
        <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-3">
          <p className="text-xs text-violet-400 font-medium mb-0.5">Recommended focus</p>
          <p className="text-sm text-white mb-1 truncate">{recommended_focus.concept}</p>
          <p className="text-xs text-gray-400">{recommended_focus.rationale}</p>
          <p className="text-xs text-gray-500 mt-1">
            Current mastery: {Math.round(recommended_focus.mastery * 100)}%
          </p>
        </div>
      )}

      {next_reviews && next_reviews.length > 0 && (
        <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-3">
          <p className="text-xs text-violet-400 font-medium mb-2">Upcoming reviews</p>
          <div className="space-y-2">
            {next_reviews.map((r, i) => (
              <div key={i} className="flex items-start justify-between gap-2">
                <p className="text-xs text-gray-300 truncate flex-1">{r.question_text}</p>
                <span className="text-xs text-gray-500 shrink-0">{fmtDue(r.due)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
