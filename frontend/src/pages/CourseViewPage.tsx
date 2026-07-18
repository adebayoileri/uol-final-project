import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  generateQuestions,
  getCourse,
  getQuestions,
  type CourseResponse,
  type QuestionResponse,
} from '../api'
import CodeBlock from '../components/CodeBlock'
import SearchPanel from '../components/SearchPanel'

function CourseViewPage() {
  const { courseId } = useParams<{ courseId: string }>()
  const [course, setCourse] = useState<CourseResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [questionsByLesson, setQuestionsByLesson] = useState<Record<string, QuestionResponse[]>>({})
  const [lessonLoading, setLessonLoading] = useState<string | null>(null)
  const [lessonError, setLessonError] = useState<string | null>(null)

  useEffect(() => {
    if (!courseId) return
    setLoading(true)
    setError(null)
    getCourse(courseId)
      .then(setCourse)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load course.'))
      .finally(() => setLoading(false))
  }, [courseId])

  async function handleGenerateQuestions(lessonId: string) {
    setLessonLoading(lessonId)
    setLessonError(null)
    try {
      const questions = await generateQuestions(lessonId)
      setQuestionsByLesson((prev) => ({ ...prev, [lessonId]: questions }))
    } catch (err) {
      setLessonError(err instanceof Error ? err.message : 'Failed to generate questions.')
    } finally {
      setLessonLoading(null)
    }
  }

  async function handleShowQuestions(lessonId: string) {
    setLessonLoading(lessonId)
    setLessonError(null)
    try {
      const questions = await getQuestions(lessonId)
      setQuestionsByLesson((prev) => ({ ...prev, [lessonId]: questions }))
    } catch (err) {
      setLessonError(err instanceof Error ? err.message : 'Failed to load questions.')
    } finally {
      setLessonLoading(null)
    }
  }

  if (loading) {
    return <p className="text-sm text-gray-400">Loading course…</p>
  }

  if (error) {
    return <p className="text-sm text-red-400">{error}</p>
  }

  if (!course) {
    return null
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-white">{course.title}</h1>
      <p className="mt-1 text-sm text-gray-400">{course.description}</p>
      <Link to="/review" className="mt-4 inline-block text-sm font-medium text-violet-400 hover:text-violet-300">
        Go to review session
      </Link>

      <SearchPanel courseId={course.id} />

      {lessonError && <p className="mt-4 text-sm text-red-400">{lessonError}</p>}

      <div className="mt-6 space-y-6">
        {course.modules.map((module) => (
          <section key={module.id} className="rounded-xl border border-[#2a2a3a] bg-[#111118] p-5">
            <h2 className="text-lg font-medium text-white">{module.title}</h2>
            <p className="mt-1 text-sm text-gray-400">{module.description}</p>

            <div className="mt-4 space-y-4">
              {module.lessons.map((lesson) => {
                const questions = questionsByLesson[lesson.id]
                const isLoading = lessonLoading === lesson.id
                return (
                  <div key={lesson.id} className="rounded-lg border border-[#2a2a3a] bg-[#1a1a24] p-4">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-medium text-white">{lesson.title}</h3>
                      <span className="shrink-0 text-xs text-gray-500">{lesson.duration_minutes} min</span>
                    </div>
                    <p className="mt-1 text-sm text-gray-400">{lesson.description}</p>
                    <ul className="mt-2 space-y-1 text-sm text-gray-400">
                      {lesson.objectives.map((objective) => (
                        <li key={objective.id} className="flex gap-2">
                          <span className="mt-0.5 shrink-0 text-gray-600">•</span>
                          {objective.description}
                        </li>
                      ))}
                    </ul>

                    <div className="mt-4 flex gap-3">
                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={() => handleGenerateQuestions(lesson.id)}
                        className="rounded-lg bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
                      >
                        {isLoading ? 'Working…' : 'Generate questions'}
                      </button>
                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={() => handleShowQuestions(lesson.id)}
                        className="rounded-lg border border-[#2a2a3a] px-3 py-1.5 text-sm font-medium text-gray-300 hover:bg-[#1a1a24] hover:text-white disabled:opacity-50"
                      >
                        Show questions
                      </button>
                    </div>

                    {questions && questions.length > 0 && (
                      <ol className="mt-4 space-y-2 text-sm">
                        {questions.map((q) => (
                          <li key={q.id} className="rounded-lg border border-[#2a2a3a] bg-[#0a0a0f] p-3">
                            <div className="flex items-center gap-2">
                              <p className="font-medium text-white">{q.text}</p>
                              {q.question_type === 'fill_blank' && (
                                <span className="rounded-full bg-violet-900/50 px-2 py-0.5 text-xs font-medium text-violet-300">
                                  Fill blank
                                </span>
                              )}
                            </div>
                            {q.question_type === 'fill_blank' && q.code_snippet && (
                              <div className="mt-2">
                                <CodeBlock code={q.code_snippet} />
                              </div>
                            )}
                            <p className="mt-2 text-gray-400">
                              <span className="text-xs uppercase tracking-wide text-gray-600">Answer: </span>
                              {q.reference_answer}
                            </p>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}

export default CourseViewPage
