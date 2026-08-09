import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  getCourse,
  getMastery,
  getAchievements,
  getReviewQueue,
  CourseSummaryResponse,
  MasteryResponse,
  AchievementResponse,
  ReviewQueueResponse,
  CourseResponse,
} from '../api'
import MasteryBar from '../components/MasteryBar'
import AchievementCard from '../components/AchievementCard'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export default function CompletionScreen() {
  const { courseId } = useParams<{ courseId: string }>()
  const navigate = useNavigate()

  const [course, setCourse] = useState<CourseResponse | null>(null)
  const [mastery, setMastery] = useState<MasteryResponse | null>(null)
  const [achievements, setAchievements] = useState<AchievementResponse[]>([])
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    if (!courseId) return
    Promise.all([
      getCourse(courseId),
      getMastery(courseId),
      getAchievements(),
      getReviewQueue(courseId),
    ])
      .then(([c, m, a, q]) => {
        setCourse(c)
        setMastery(m)
        setAchievements(a)
        setQueue(q)
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [courseId])

  async function handleDownload() {
    if (!courseId) return
    setDownloading(true)
    try {
      const res = await fetch(`${API_URL}/courses/${courseId}/certificate`)
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.detail ?? `Error ${res.status}`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `certificate-${courseId}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed')
    } finally {
      setDownloading(false)
    }
  }

  if (loading) return <p className="text-sm text-gray-400">Loading…</p>
  if (error) return <p className="text-sm text-red-400">{error}</p>
  if (!course) return null

  const totalLessons = course.modules.reduce((sum, m) => sum + m.lessons.length, 0)
  const unlockedAchievements = achievements.filter((a) => a.unlocked)
  const masteryPct = mastery ? Math.round(mastery.overall * 100) : 0

  return (
    <div className="space-y-8">
      {/* Celebration banner */}
      <div className="rounded-xl border border-violet-700 bg-violet-900/20 p-6 text-center">
        <p className="text-3xl mb-2">🎉</p>
        <h1 className="text-2xl font-bold text-white mb-1">Course Complete!</h1>
        <p className="text-sm text-gray-400">{course.title}</p>
      </div>

      {/* Stat tiles */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-4 text-center">
          <p className="text-2xl font-bold text-white">{totalLessons}</p>
          <p className="text-xs text-gray-500 mt-0.5">Lessons</p>
        </div>
        <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-4 text-center">
          <p className="text-2xl font-bold text-violet-400">{masteryPct}%</p>
          <p className="text-xs text-gray-500 mt-0.5">Mastery</p>
        </div>
        <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-4 text-center">
          <p className="text-2xl font-bold text-white">{queue?.total ?? 0}</p>
          <p className="text-xs text-gray-500 mt-0.5">Cards to review</p>
        </div>
      </div>

      {/* Achievements */}
      {unlockedAchievements.length > 0 && (
        <section>
          <h2 className="text-xs text-gray-500 uppercase tracking-wider mb-3">Achievements earned</h2>
          <div className="space-y-2">
            {unlockedAchievements.map((a) => (
              <AchievementCard key={a.id} {...a} />
            ))}
          </div>
        </section>
      )}

      {/* Mastery breakdown */}
      {mastery && mastery.concepts.length > 0 && (
        <section>
          <h2 className="text-xs text-gray-500 uppercase tracking-wider mb-3">Knowledge mastery</h2>
          <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-4 space-y-3">
            {mastery.concepts.slice(0, 10).map((c, i) => (
              <MasteryBar key={i} name={c.name} mastery={c.mastery} />
            ))}
          </div>
        </section>
      )}

      {/* Actions */}
      <div className="flex flex-col gap-3">
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="w-full rounded-lg border border-violet-600 px-5 py-3 text-sm font-medium text-violet-400 hover:bg-violet-900/20 disabled:opacity-60 transition-colors"
        >
          {downloading ? 'Generating PDF…' : 'Download Certificate'}
        </button>
        <Link
          to={`/courses/${courseId}/review`}
          className="w-full rounded-lg bg-violet-600 px-5 py-3 text-sm font-medium text-white hover:bg-violet-500 transition-colors text-center"
        >
          Review cards
        </Link>
        <Link
          to="/"
          className="w-full rounded-lg border border-[#2a2a3a] px-5 py-3 text-sm font-medium text-gray-400 hover:text-white hover:border-violet-600 transition-colors text-center"
        >
          Start a new course
        </Link>
      </div>
    </div>
  )
}
