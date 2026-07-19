import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { createCourse, getCourses, type CourseRequest } from '../api'

const inputClass =
  'mt-1 block w-full rounded-lg border border-[#2a2a3a] bg-[#1a1a24] px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none'

export default function Home() {
  const navigate = useNavigate()
  const [hasCourses, setHasCourses] = useState(false)
  const [goal, setGoal] = useState('')
  const [duration, setDuration] = useState<CourseRequest['duration']>('short_term')
  const [category, setCategory] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getCourses()
      .then((courses) => setHasCourses(courses.length > 0))
      .catch(() => {})
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const course = await createCourse({ goal, duration, category })
      navigate(`/courses/${course.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate course.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      {hasCourses && (
        <div className="mb-8 flex gap-3">
          <Link
            to="/courses"
            className="rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-violet-500"
          >
            Continue learning
          </Link>
        </div>
      )}

      <h1 className="text-2xl font-semibold text-white">
        {hasCourses ? 'Start a new goal' : 'What do you want to learn?'}
      </h1>
      <p className="mt-1 text-sm text-gray-400">
        Describe your goal and we'll generate a structured course for you.
      </p>

      <form onSubmit={handleSubmit} className="mt-6">
        <div className="rounded-xl border border-[#2a2a3a] bg-[#111118] p-6 space-y-4">
          <div>
            <label htmlFor="goal" className="block text-sm font-medium text-gray-300">
              Goal
            </label>
            <textarea
              id="goal"
              required
              minLength={10}
              maxLength={1000}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              rows={4}
              className={inputClass}
              placeholder="e.g. Learn Python to automate repetitive tasks at work"
            />
          </div>

          <div>
            <label htmlFor="duration" className="block text-sm font-medium text-gray-300">
              Duration
            </label>
            <select
              id="duration"
              value={duration}
              onChange={(e) => setDuration(e.target.value as CourseRequest['duration'])}
              className={inputClass}
            >
              <option value="short_term">Short term</option>
              <option value="long_term">Long term</option>
            </select>
          </div>

          <div>
            <label htmlFor="category" className="block text-sm font-medium text-gray-300">
              Category
            </label>
            <input
              id="category"
              type="text"
              required
              minLength={2}
              maxLength={100}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={inputClass}
              placeholder="e.g. Programming"
            />
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-violet-600 px-5 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
          >
            {loading ? 'Generating course…' : 'Generate course'}
          </button>
        </div>
      </form>
    </div>
  )
}
