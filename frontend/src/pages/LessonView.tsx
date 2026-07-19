import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  getLessonDetail,
  generateQuestions,
  answerQuestion,
  completeLesson,
  LessonDetailResponse,
  QuestionResponse,
  AnswerResponse,
} from '../api'
import CodeBlock from '../components/CodeBlock'

type Phase = 'answering' | 'feedback'

export default function LessonView() {
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>()
  const navigate = useNavigate()

  const [lesson, setLesson] = useState<LessonDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [questionsOpen, setQuestionsOpen] = useState(false)
  const [qIndex, setQIndex] = useState<number>(() => {
    const saved = lessonId ? localStorage.getItem(`lesson-${lessonId}-qi`) : null
    return saved ? parseInt(saved, 10) : 0
  })

  const [generating, setGenerating] = useState(false)
  const [completing, setCompleting] = useState(false)

  const [phase, setPhase] = useState<Phase>('answering')
  const [userAnswer, setUserAnswer] = useState('')
  const [checking, setChecking] = useState(false)
  const [feedback, setFeedback] = useState<AnswerResponse | null>(null)

  const fetchLesson = useCallback(() => {
    if (!courseId || !lessonId) return
    getLessonDetail(courseId, lessonId)
      .then(setLesson)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [courseId, lessonId])

  useEffect(() => { fetchLesson() }, [fetchLesson])

  useEffect(() => {
    if (lessonId) localStorage.setItem(`lesson-${lessonId}-qi`, String(qIndex))
  }, [lessonId, qIndex])

  async function handleGenerate() {
    if (!lessonId) return
    setGenerating(true)
    try {
      await generateQuestions(lessonId)
      setLoading(true)
      fetchLesson()
      setQuestionsOpen(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed.')
    } finally {
      setGenerating(false)
    }
  }

  async function handleCheckAnswer(q: QuestionResponse) {
    if (!userAnswer.trim()) return
    setChecking(true)
    try {
      const result = await answerQuestion(q.id, userAnswer)
      setFeedback(result)
      setPhase('feedback')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Check failed.')
    } finally {
      setChecking(false)
    }
  }

  function handleNext(questions: QuestionResponse[]) {
    const next = qIndex + 1 < questions.length ? qIndex + 1 : qIndex
    setQIndex(next)
    setPhase('answering')
    setUserAnswer('')
    setFeedback(null)
  }

  function handlePrev() {
    const prev = qIndex - 1 >= 0 ? qIndex - 1 : 0
    setQIndex(prev)
    setPhase('answering')
    setUserAnswer('')
    setFeedback(null)
  }

  async function handleComplete() {
    if (!lessonId) return
    setCompleting(true)
    try {
      await completeLesson(lessonId)
      navigate(`/courses/${courseId}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not mark complete.')
    } finally {
      setCompleting(false)
    }
  }

  if (loading) return <p className="text-sm text-gray-400">Loading lesson…</p>
  if (error) return <p className="text-sm text-red-400">{error}</p>
  if (!lesson) return null

  const questions = lesson.questions
  const currentQ = questions[qIndex] ?? null

  const verdictStyle = feedback
    ? feedback.verdict === 'correct'
      ? 'bg-green-900/40 border-green-800 text-green-300'
      : feedback.score >= 0.5
      ? 'bg-yellow-900/40 border-yellow-800 text-yellow-300'
      : 'bg-red-900/40 border-red-800 text-red-300'
    : ''

  return (
    <div>
      <div className="mb-4">
        <Link to={`/courses/${courseId}`} className="text-xs text-gray-500 hover:text-gray-400">
          ← Back to course
        </Link>
      </div>

      <div className="flex items-start justify-between gap-3 mb-1">
        <h1 className="text-xl font-bold text-white">{lesson.title}</h1>
        <span className="shrink-0 text-xs bg-[#1a1a24] border border-[#2a2a3a] text-gray-400 px-2 py-1 rounded">
          ~{lesson.duration_minutes}m
        </span>
      </div>

      {lesson.objectives.length > 0 && (
        <div className="mt-4 rounded-lg border border-[#2a2a3a] bg-[#111118] p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Objectives</p>
          <ul className="space-y-1">
            {lesson.objectives.map((obj) => (
              <li key={obj.id} className="flex gap-2 text-sm text-gray-300">
                <span className="text-violet-400 mt-0.5">•</span>
                {obj.description}
              </li>
            ))}
          </ul>
        </div>
      )}

      {lesson.description && (
        <p className="mt-4 text-sm text-gray-400 whitespace-pre-wrap leading-relaxed">
          {lesson.description}
        </p>
      )}

      <div className="mt-6">
        {questions.length === 0 ? (
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="rounded-lg border border-[#2a2a3a] bg-[#111118] px-4 py-2.5 text-sm text-gray-300 hover:border-violet-600 hover:text-white disabled:opacity-60 transition-colors"
          >
            {generating ? 'Generating…' : 'Generate questions'}
          </button>
        ) : (
          <div>
            <button
              onClick={() => setQuestionsOpen((o) => !o)}
              className="flex items-center gap-2 text-sm text-gray-300 hover:text-white"
            >
              <svg
                className={`w-4 h-4 transition-transform ${questionsOpen ? 'rotate-90' : ''}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              Study questions ({questions.length})
            </button>

            {questionsOpen && currentQ && (
              <div className="mt-4 rounded-lg border border-[#2a2a3a] bg-[#111118] p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex gap-1">
                    <button
                      onClick={handlePrev}
                      disabled={qIndex === 0}
                      className="px-2 py-1 text-xs text-gray-400 hover:text-white disabled:opacity-30"
                    >
                      ← Prev
                    </button>
                    <button
                      onClick={() => handleNext(questions)}
                      disabled={qIndex >= questions.length - 1}
                      className="px-2 py-1 text-xs text-gray-400 hover:text-white disabled:opacity-30"
                    >
                      Next →
                    </button>
                  </div>
                  <span className="text-xs text-gray-500">
                    {qIndex + 1} / {questions.length}
                  </span>
                </div>

                {currentQ.question_type === 'fill_blank' && currentQ.code_snippet && (
                  <div className="mb-3">
                    <CodeBlock code={currentQ.code_snippet} language="python" />
                  </div>
                )}

                <p className="text-sm text-white mb-4">{currentQ.text}</p>

                {phase === 'answering' && (
                  <>
                    {currentQ.question_type === 'fill_blank' ? (
                      <input
                        type="text"
                        value={userAnswer}
                        onChange={(e) => setUserAnswer(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleCheckAnswer(currentQ)}
                        placeholder="Your answer…"
                        className="w-full rounded-lg border border-[#2a2a3a] bg-[#1a1a24] px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none font-mono"
                      />
                    ) : (
                      <textarea
                        value={userAnswer}
                        onChange={(e) => setUserAnswer(e.target.value)}
                        rows={3}
                        placeholder="Your answer…"
                        className="w-full rounded-lg border border-[#2a2a3a] bg-[#1a1a24] px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none resize-none"
                      />
                    )}
                    <button
                      onClick={() => handleCheckAnswer(currentQ)}
                      disabled={checking || !userAnswer.trim()}
                      className="mt-3 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
                    >
                      {checking ? 'Checking…' : 'Check answer'}
                    </button>
                  </>
                )}

                {phase === 'feedback' && feedback && (
                  <div className="space-y-3">
                    <div className={`rounded-lg border p-3 text-sm ${verdictStyle}`}>
                      <div className="font-medium">
                        {feedback.verdict === 'correct' ? 'Correct' : `Score: ${Math.round(feedback.score * 100)}%`}
                      </div>
                      {feedback.explanation && (
                        <p className="mt-1 text-xs opacity-80">{feedback.explanation}</p>
                      )}
                    </div>
                    <div className="text-sm text-gray-400">
                      <span className="text-xs text-gray-500 uppercase tracking-wider">Reference</span>
                      <p className="mt-1">{currentQ.reference_answer}</p>
                    </div>
                    <button
                      onClick={() => handleNext(questions)}
                      className="text-sm text-violet-400 hover:text-violet-300"
                    >
                      {qIndex < questions.length - 1 ? 'Next question →' : 'Done'}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mt-10">
        {lesson.completed_at ? (
          <div className="flex items-center gap-2 text-sm text-green-400">
            <span>✓</span>
            <span>Completed</span>
          </div>
        ) : (
          <button
            onClick={handleComplete}
            disabled={completing}
            className="w-full rounded-lg bg-violet-600 px-5 py-3 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
          >
            {completing ? 'Saving…' : 'Mark complete'}
          </button>
        )}
      </div>
    </div>
  )
}
