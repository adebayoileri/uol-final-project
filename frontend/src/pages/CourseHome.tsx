import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getCourse, getReviewQueue, CourseResponse, ReviewQueueResponse } from '../api'
import InsightsPanel from '../components/InsightsPanel'

export default function CourseHome() {
  const { courseId } = useParams<{ courseId: string }>()
  const navigate = useNavigate()
  const [course, setCourse] = useState<CourseResponse | null>(null)
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!courseId) return
    Promise.all([getCourse(courseId), getReviewQueue(courseId)])
      .then(([c, q]) => { setCourse(c); setQueue(q) })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [courseId])

  if (!courseId) return <p className="text-sm text-red-400">No course selected.</p>
  if (loading) return <p className="text-sm text-gray-400">Loading…</p>
  if (error) return <p className="text-sm text-red-400">{error}</p>
  if (!course) return null

  const nextLesson = (() => {
    for (const mod of course.modules) {
      for (const lesson of mod.lessons) {
        if (!lesson.completed_at) return { id: lesson.id, title: lesson.title }
      }
    }
    return null
  })()

  const dueNow = queue?.due_now ?? 0

  return (
    <div>
      <div className="mb-2">
        <Link to="/courses" className="text-xs text-gray-500 hover:text-gray-400">
          ← Courses
        </Link>
      </div>

      <h1 className="text-2xl font-bold text-white">{course.title}</h1>
      <p className="mt-1 text-sm text-gray-400">{course.description}</p>

      <div className="mt-6 space-y-3">
        {nextLesson ? (
          <div>
            <button
              onClick={() => navigate(`/courses/${courseId}/lessons/${nextLesson.id}`)}
              className="rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-violet-500"
            >
              Continue
            </button>
            <p className="mt-1.5 text-xs text-gray-500">Next: {nextLesson.title}</p>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-green-400">
            <span>✓</span>
            <span>All lessons complete — keep reviewing to reinforce your knowledge.</span>
          </div>
        )}
        <div className="flex gap-2 flex-wrap">
          <Link
            to={`/courses/${courseId}/timeline`}
            className="rounded-lg px-4 py-2 text-sm font-medium bg-[#1a1a24] border border-[#2a2a3a] text-gray-400 hover:border-violet-600 hover:text-white"
          >
            Timeline
          </Link>
        </div>
        <div>
          <button
            onClick={() => dueNow > 0 && navigate(`/courses/${courseId}/review`)}
            disabled={dueNow === 0}
            className={`rounded-lg px-5 py-2.5 text-sm font-medium ${
              dueNow > 0
                ? 'bg-[#1a1a24] border border-[#2a2a3a] text-white hover:border-violet-600'
                : 'bg-[#111118] border border-[#2a2a3a] text-gray-500 cursor-not-allowed'
            }`}
          >
            {dueNow > 0 ? `Review ${dueNow} card${dueNow === 1 ? '' : 's'}` : 'No cards due'}
          </button>
        </div>
      </div>

      <div className="mt-8 space-y-4">
        {course.modules.map((mod, mi) => (
          <div key={mod.id} className="rounded-lg border border-[#2a2a3a] bg-[#111118] overflow-hidden">
            <div className="px-5 py-3 border-b border-[#2a2a3a]">
              <span className="text-xs text-gray-500 uppercase tracking-wider">
                Module {mi + 1}
              </span>
              <h2 className="text-sm font-semibold text-white mt-0.5">{mod.title}</h2>
            </div>
            <ul className="divide-y divide-[#2a2a3a]">
              {mod.lessons.map((lesson) => (
                <li key={lesson.id}>
                  <Link
                    to={`/courses/${courseId}/lessons/${lesson.id}`}
                    className="flex items-center gap-3 px-5 py-3 hover:bg-[#1a1a24] transition-colors"
                  >
                    <span className={`shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                      lesson.completed_at
                        ? 'bg-green-900/50 text-green-400'
                        : 'border border-[#2a2a3a] text-transparent'
                    }`}>
                      {lesson.completed_at ? '✓' : ''}
                    </span>
                    <span className="flex-1 text-sm text-gray-200">{lesson.title}</span>
                    <span className="text-xs text-gray-500">~{lesson.duration_minutes}m</span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <InsightsPanel courseId={courseId} />
    </div>
  )
}
