import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

interface TimelineLesson {
  id: string
  title: string
  duration_minutes: number
  completed_at: string | null
  order_index: number
}

interface TimelineModule {
  title: string
  lessons: TimelineLesson[]
}

interface TimelineData {
  modules: TimelineModule[]
  total_minutes: number
  completed_minutes: number
  streak: number
}

export default function CourseTimeline() {
  const { courseId } = useParams<{ courseId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<TimelineData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!courseId) return
    fetch(`${API_URL}/courses/${courseId}/timeline`)
      .then((r) => r.json())
      .then(setData)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [courseId])

  if (loading) return <p className="text-sm text-gray-400">Loading timeline…</p>
  if (error) return <p className="text-sm text-red-400">{error}</p>
  if (!data) return null

  const totalLessons = data.modules.reduce((s, m) => s + m.lessons.length, 0)
  const completedLessons = data.modules.reduce(
    (s, m) => s + m.lessons.filter((l) => l.completed_at).length,
    0,
  )
  const progressPct = totalLessons > 0 ? Math.round((completedLessons / totalLessons) * 100) : 0
  const remainingMins = data.total_minutes - data.completed_minutes

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-2">
        <Link to={`/courses/${courseId}`} className="text-xs text-gray-500 hover:text-gray-400">
          ← Back to course
        </Link>
      </div>

      <h1 className="text-xl font-bold text-white">Timeline</h1>

      {/* Stat tiles */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-3 text-center">
          <p className="text-xl font-bold text-violet-400">{progressPct}%</p>
          <p className="text-xs text-gray-500 mt-0.5">Progress</p>
        </div>
        <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-3 text-center">
          <p className="text-xl font-bold text-white">{remainingMins}m</p>
          <p className="text-xs text-gray-500 mt-0.5">Time left</p>
        </div>
        <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-3 text-center">
          <p className="text-xl font-bold text-white">{data.streak}</p>
          <p className="text-xs text-gray-500 mt-0.5">Day streak</p>
        </div>
      </div>

      {/* Overall progress bar */}
      <div>
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>{completedLessons} of {totalLessons} lessons complete</span>
          <span>{progressPct}%</span>
        </div>
        <div className="h-2 bg-[#1a1a24] rounded-full overflow-hidden">
          <div
            className="h-full bg-violet-600 rounded-full transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Vertical timeline */}
      <div className="space-y-6">
        {data.modules.map((module, mi) => (
          <div key={mi}>
            <h2 className="text-xs text-gray-500 uppercase tracking-wider mb-3 pl-6">
              {module.title}
            </h2>
            <div className="space-y-0">
              {module.lessons.map((lesson, li) => {
                const done = !!lesson.completed_at
                const isLast = li === module.lessons.length - 1
                return (
                  <div key={lesson.id} className="flex gap-3">
                    {/* Timeline column */}
                    <div className="flex flex-col items-center">
                      <div
                        className={`w-4 h-4 rounded-full shrink-0 flex items-center justify-center border-2 transition-colors ${
                          done
                            ? 'bg-green-600 border-green-600'
                            : 'bg-[#111118] border-[#2a2a3a]'
                        }`}
                      >
                        {done && (
                          <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 10 10">
                            <path d="M2 5l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        )}
                      </div>
                      {!isLast && (
                        <div className="w-px flex-1 bg-[#2a2a3a] my-1" />
                      )}
                    </div>

                    {/* Lesson card */}
                    <div className={`flex-1 pb-4 ${isLast ? '' : ''}`}>
                      <button
                        onClick={() => navigate(`/courses/${courseId}/lessons/${lesson.id}`)}
                        className="w-full text-left rounded-lg border border-[#2a2a3a] bg-[#111118] px-3 py-2.5 hover:border-violet-600 transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <span className={`text-sm ${done ? 'text-gray-400 line-through' : 'text-white'}`}>
                            {lesson.title}
                          </span>
                          <span className="text-xs text-gray-500 shrink-0 ml-2">
                            ~{lesson.duration_minutes}m
                          </span>
                        </div>
                        {done && lesson.completed_at && (
                          <p className="text-xs text-green-500 mt-0.5">
                            Completed {new Date(lesson.completed_at).toLocaleDateString()}
                          </p>
                        )}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
