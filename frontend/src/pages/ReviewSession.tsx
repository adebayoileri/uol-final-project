import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getNextCard, getReviewQueue, answerQuestion, gradeCard, CardResponse, AnswerResponse } from '../api'
import CodeBlock from '../components/CodeBlock'

type Phase = 'answering' | 'feedback' | 'empty' | 'done'

const RATINGS = [
  { label: 'Again', value: 1, key: '1', style: 'border-red-800 text-red-300 hover:bg-red-900/40' },
  { label: 'Hard', value: 2, key: '2', style: 'border-orange-800 text-orange-300 hover:bg-orange-900/40' },
  { label: 'Good', value: 3, key: '3', style: 'border-green-800 text-green-300 hover:bg-green-900/40' },
  { label: 'Easy', value: 4, key: '4', style: 'border-blue-800 text-blue-300 hover:bg-blue-900/40' },
]

export default function ReviewSession() {
  const { courseId } = useParams<{ courseId?: string }>()

  const [phase, setPhase] = useState<Phase>('answering')
  const [card, setCard] = useState<CardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [sessionTotal, setSessionTotal] = useState(0)
  const [graded, setGraded] = useState(0)
  const [userAnswer, setUserAnswer] = useState('')
  const [checking, setChecking] = useState(false)
  const [feedback, setFeedback] = useState<AnswerResponse | null>(null)
  const [grading, setGrading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const loadNextCard = useCallback(async () => {
    try {
      const next = await getNextCard(courseId)
      if (!next) {
        setPhase('done')
      } else {
        setCard(next)
        setPhase('answering')
        setUserAnswer('')
        setFeedback(null)
        setTimeout(() => textareaRef.current?.focus(), 50)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load card.')
    }
  }, [courseId])

  useEffect(() => {
    async function init() {
      try {
        const queue = await getReviewQueue(courseId)
        setSessionTotal(queue.due_now)
        if (queue.due_now === 0) {
          setPhase('empty')
          return
        }
        await loadNextCard()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to start session.')
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [courseId, loadNextCard])

  async function handleCheckAnswer() {
    if (!card || !userAnswer.trim()) return
    setChecking(true)
    try {
      const result = await answerQuestion(card.question_id, userAnswer)
      setFeedback(result)
      setPhase('feedback')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Check failed.')
    } finally {
      setChecking(false)
    }
  }

  async function handleGrade(rating: number) {
    if (!card) return
    setGrading(true)
    try {
      await gradeCard(card.id, rating)
      setGraded((g) => g + 1)
      await loadNextCard()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Grading failed.')
    } finally {
      setGrading(false)
    }
  }

  // Keeps the keydown listener off `handleGrade` as a dep without going stale.
  const handleGradeRef = useRef(handleGrade)
  useLayoutEffect(() => {
    handleGradeRef.current = handleGrade
  })

  useEffect(() => {
    if (phase !== 'feedback') return
    function onKey(e: KeyboardEvent) {
      // Don't hijack digits the user is typing into a field.
      if (e.target instanceof HTMLElement && e.target.closest('input, textarea, [contenteditable]')) {
        return
      }
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const rating = parseInt(e.key, 10)
      if (rating >= 1 && rating <= 4 && !grading) {
        handleGradeRef.current(rating)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [phase, grading])

  const backLink = courseId ? `/courses/${courseId}` : '/courses'

  if (loading) return <p className="text-sm text-gray-400">Loading session…</p>
  if (error) return <p className="text-sm text-red-400">{error}</p>

  if (phase === 'empty') {
    return (
      <div className="text-center py-16">
        <p className="text-gray-400 mb-4">No cards due for review.</p>
        <Link to={backLink} className="text-violet-400 hover:text-violet-300 text-sm">
          ← Back
        </Link>
      </div>
    )
  }

  if (phase === 'done') {
    return (
      <div className="text-center py-16">
        <p className="text-white font-semibold text-lg mb-2">Session complete</p>
        <p className="text-gray-400 text-sm mb-6">{graded} card{graded !== 1 ? 's' : ''} reviewed</p>
        <Link to={backLink} className="text-violet-400 hover:text-violet-300 text-sm">
          ← Back
        </Link>
      </div>
    )
  }

  if (!card) return null

  const isFillBlank = card.question_type === 'fill_blank'

  const verdictStyle = feedback
    ? feedback.verdict === 'correct'
      ? 'bg-green-900/40 border-green-800 text-green-300'
      : feedback.score >= 0.5
      ? 'bg-yellow-900/40 border-yellow-800 text-yellow-300'
      : 'bg-red-900/40 border-red-800 text-red-300'
    : ''

  return (
    <div>
      {sessionTotal > 0 && (
        <div className="mb-6">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>{graded} / {sessionTotal} reviewed</span>
            <Link to={backLink} className="text-gray-500 hover:text-gray-400">End session</Link>
          </div>
          <div className="h-1.5 bg-[#2a2a3a] rounded-full overflow-hidden">
            <div
              className="h-full bg-violet-600 rounded-full transition-all"
              style={{ width: `${Math.round((graded / sessionTotal) * 100)}%` }}
            />
          </div>
        </div>
      )}

      <div className="rounded-xl border border-[#2a2a3a] bg-[#111118] p-6">
        {isFillBlank && card.code_snippet && (
          <div className="mb-4">
            <CodeBlock code={card.code_snippet} language="python" />
          </div>
        )}

        <p className="text-white text-base mb-6">{card.question_text}</p>

        {phase === 'answering' && (
          <>
            {isFillBlank ? (
              <input
                type="text"
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCheckAnswer()}
                placeholder="Your answer…"
                className="w-full rounded-lg border border-[#2a2a3a] bg-[#1a1a24] px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none font-mono"
                autoFocus
              />
            ) : (
              <textarea
                ref={textareaRef}
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
                rows={4}
                placeholder="Your answer…"
                className="w-full rounded-lg border border-[#2a2a3a] bg-[#1a1a24] px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none resize-none"
              />
            )}
            <button
              onClick={handleCheckAnswer}
              disabled={checking || !userAnswer.trim()}
              className="mt-4 rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
            >
              {checking ? 'Checking…' : 'Check answer'}
            </button>
          </>
        )}

        {phase === 'feedback' && feedback && (
          <div className="space-y-4">
            <div className={`rounded-lg border p-3 text-sm ${verdictStyle}`}>
              <div className="font-medium">
                {feedback.verdict === 'correct' ? 'Correct' : `Score: ${Math.round(feedback.score * 100)}%`}
              </div>
              {feedback.explanation && (
                <p className="mt-1 text-xs opacity-80">{feedback.explanation}</p>
              )}
            </div>

            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Reference answer</p>
              <p className="text-sm text-gray-300">{card.question_reference_answer}</p>
            </div>

            <div>
              <p className="text-xs text-gray-500 mb-2">Rate your recall (1–4):</p>
              <div className="grid grid-cols-4 gap-2">
                {RATINGS.map(({ label, value, key, style }) => (
                  <button
                    key={value}
                    onClick={() => handleGrade(value)}
                    disabled={grading}
                    className={`rounded-lg border py-2.5 text-sm font-medium ${style} disabled:opacity-60 transition-colors`}
                  >
                    <span className="block text-xs opacity-60 mb-0.5">{key}</span>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
