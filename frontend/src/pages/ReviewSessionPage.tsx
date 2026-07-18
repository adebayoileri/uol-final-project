import { useCallback, useEffect, useRef, useState } from 'react'
import { answerQuestion, gradeCard, getNextCard, type AnswerResponse, type CardResponse } from '../api'
import CodeBlock from '../components/CodeBlock'

const RATINGS: { label: string; value: number }[] = [
  { label: 'Again', value: 1 },
  { label: 'Hard', value: 2 },
  { label: 'Good', value: 3 },
  { label: 'Easy', value: 4 },
]

type Phase = 'answering' | 'feedback'

function ReviewSessionPage() {
  const [card, setCard] = useState<CardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [phase, setPhase] = useState<Phase>('answering')
  const [userAnswer, setUserAnswer] = useState('')
  const [checking, setChecking] = useState(false)
  const [feedback, setFeedback] = useState<AnswerResponse | null>(null)

  const [grading, setGrading] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const loadNextCard = useCallback(() => {
    setLoading(true)
    setError(null)
    setPhase('answering')
    setUserAnswer('')
    setFeedback(null)
    getNextCard()
      .then(setCard)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load next card.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadNextCard()
  }, [loadNextCard])

  useEffect(() => {
    if (!loading && card && phase === 'answering') {
      textareaRef.current?.focus()
    }
  }, [loading, card, phase])

  async function handleCheckAnswer() {
    if (!card || !userAnswer.trim()) return
    setChecking(true)
    setError(null)
    try {
      const result = await answerQuestion(card.question_id, userAnswer.trim())
      setFeedback(result)
      setPhase('feedback')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to check answer.')
    } finally {
      setChecking(false)
    }
  }

  async function handleGrade(rating: number) {
    if (!card) return
    setGrading(true)
    setError(null)
    try {
      await gradeCard(card.id, rating)
      loadNextCard()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit rating.')
    } finally {
      setGrading(false)
    }
  }

  if (loading) {
    return <p className="text-sm text-gray-400">Loading next card…</p>
  }

  if (error) {
    return (
      <div>
        <p className="text-sm text-red-400">{error}</p>
        <button
          type="button"
          onClick={loadNextCard}
          className="mt-3 rounded-lg border border-[#2a2a3a] px-3 py-1.5 text-sm font-medium text-gray-300 hover:bg-[#1a1a24]"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!card) {
    return (
      <div>
        <h1 className="text-2xl font-semibold text-white">Review</h1>
        <p className="mt-6 text-sm text-gray-400">No cards due right now.</p>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-white">Review</h1>

      {/* Question */}
      <div className="mt-6 rounded-xl border border-[#2a2a3a] bg-[#111118] p-6">
        <p className="text-lg text-white">{card.question_text}</p>
        {card.question_type === 'fill_blank' && card.code_snippet && (
          <div className="mt-3">
            <CodeBlock code={card.code_snippet} />
          </div>
        )}
      </div>

      {phase === 'answering' && (
        <div className="mt-4 space-y-3">
          {card.question_type === 'fill_blank' ? (
            <input
              autoFocus
              type="text"
              value={userAnswer}
              onChange={(e) => setUserAnswer(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleCheckAnswer() }}
              placeholder="Type the missing line…"
              className="block w-full rounded-lg border border-[#2a2a3a] bg-[#1a1a24] px-3 py-2 font-mono text-sm text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none"
            />
          ) : (
          <textarea
            ref={textareaRef}
            value={userAnswer}
            onChange={(e) => setUserAnswer(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleCheckAnswer()
            }}
            rows={4}
            placeholder="Type your answer…"
            className="block w-full rounded-lg border border-[#2a2a3a] bg-[#1a1a24] px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none"
          />
          )}
          <button
            type="button"
            disabled={checking || !userAnswer.trim()}
            onClick={handleCheckAnswer}
            className="rounded-lg bg-violet-600 px-5 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
          >
            {checking ? 'Checking…' : 'Check answer'}
          </button>
        </div>
      )}

      {phase === 'feedback' && feedback && (
        <div className="mt-4 space-y-4">
          {/* Verdict banner */}
          <div
            className={`rounded-lg border px-4 py-3 text-sm font-medium ${
              feedback.verdict === 'correct'
                ? 'border-green-800 bg-green-900/40 text-green-400'
                : 'border-red-800 bg-red-900/40 text-red-400'
            }`}
          >
            {feedback.verdict === 'correct' ? 'Correct' : 'Incorrect'}
            {feedback.signal_used !== 'llm' && (
              <span className="ml-2 font-normal opacity-75">
                (similarity {Math.round(feedback.score * 100)}%)
              </span>
            )}
            {feedback.explanation && (
              <span className="ml-2 font-normal opacity-75">— {feedback.explanation}</span>
            )}
          </div>

          {/* Your answer */}
          <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Your answer</p>
            <p className="mt-1 text-sm text-gray-300">{userAnswer}</p>
          </div>

          {/* Reference answer */}
          <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Reference answer</p>
            <p className="mt-1 text-sm text-gray-300">{card.question_reference_answer}</p>
          </div>

          {/* Rating */}
          <div>
            <p className="mb-3 text-sm font-medium text-gray-400">How well did you know it?</p>
            <div className="flex gap-3">
              {RATINGS.map((r) => (
                <button
                  key={r.value}
                  type="button"
                  disabled={grading}
                  onClick={() => handleGrade(r.value)}
                  className="rounded-lg border border-[#2a2a3a] px-4 py-2 text-sm font-medium text-gray-300 hover:bg-[#1a1a24] hover:text-white disabled:opacity-50"
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ReviewSessionPage
