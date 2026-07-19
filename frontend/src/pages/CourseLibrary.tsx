import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getCourses, CourseSummaryResponse } from '../api'

export default function CourseLibrary() {
  const [courses, setCourses] = useState<CourseSummaryResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getCourses()
      .then(setCourses)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-sm text-gray-400">Loading courses…</p>
  if (error) return <p className="text-sm text-red-400">{error}</p>

  if (courses.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-400 mb-4">You have no courses yet.</p>
        <Link to="/" className="text-violet-400 hover:text-violet-300 text-sm">
          Start a new goal →
        </Link>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Your courses</h1>
      <ul className="space-y-3">
        {courses.map((course) => {
          const { total_lessons, completed_lessons, due_now } = course.progress_summary
          const pct = total_lessons > 0 ? Math.round((completed_lessons / total_lessons) * 100) : 0

          return (
            <li key={course.id}>
              <Link
                to={`/courses/${course.id}`}
                className="block bg-[#111118] border border-[#2a2a3a] rounded-lg px-5 py-4 hover:border-violet-600 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-white font-medium truncate">{course.title}</span>
                      <span className="shrink-0 bg-[#1a1a24] text-violet-300 text-xs px-2 py-0.5 rounded">
                        {course.category}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <div className="flex-1 h-1.5 bg-[#2a2a3a] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-violet-600 rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="shrink-0 text-xs text-gray-500">
                        {completed_lessons}/{total_lessons} lessons
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {due_now > 0 && (
                      <span className="bg-amber-900/50 text-amber-300 text-xs px-2 py-0.5 rounded">
                        {due_now} due
                      </span>
                    )}
                    <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </Link>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
