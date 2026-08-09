import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import { CalendarCheck, Check, Meh, RotateCcw, Trophy, X, Zap } from 'lucide-react'
import {
  answerQuestion,
  getNextCard,
  getReviewQueue,
  gradeCard,
  type AnswerResponse,
  type CardResponse,
  type ReviewQueueResponse,
} from '../api'
import CodeBlock from '../components/CodeBlock'
import ReviewCalendar from '../components/review/ReviewCalendar'
import Confetti from '../components/review/Confetti'
import {
  Badge,
  Button,
  ButtonLink,
  Card,
  EmptyState,
  ErrorState,
  IconBadge,
  Input,
  ProgressBar,
  Skeleton,
  Textarea,
  VerdictPanel,
} from '../components/ui'
import { springDefault, springMomentum } from '../motion/springs'
import { cn } from '../lib/cn'

type Phase = 'answering' | 'feedback' | 'empty' | 'done'

/** Again → Easy reads as one ramp rather than four unrelated hues. */
const RATINGS = [
  { label: 'Again', value: 1, icon: RotateCcw, cls: 'border-rate-again/40 text-rate-again hover:bg-rate-again/12' },
  { label: 'Hard', value: 2, icon: Meh, cls: 'border-rate-hard/40 text-rate-hard hover:bg-rate-hard/12' },
  { label: 'Good', value: 3, icon: Check, cls: 'border-rate-good/40 text-rate-good hover:bg-rate-good/12' },
  { label: 'Easy', value: 4, icon: Zap, cls: 'border-rate-easy/40 text-rate-easy hover:bg-rate-easy/12' },
] as const

export default function ReviewSession() {
  const { courseId } = useParams<{ courseId?: string }>()

  const [phase, setPhase] = useState<Phase>('answering')
  const [card, setCard] = useState<CardResponse | null>(null)
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [sessionTotal, setSessionTotal] = useState(0)
  const [graded, setGraded] = useState(0)
  const [correct, setCorrect] = useState(0)
  const [userAnswer, setUserAnswer] = useState('')
  const [checking, setChecking] = useState(false)
  const [feedback, setFeedback] = useState<AnswerResponse | null>(null)
  const [grading, setGrading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  /** −1 exits left (Again), +1 exits right (Easy). */
  const [exitDir, setExitDir] = useState(0)

  const answerRef = useRef<HTMLTextAreaElement>(null)

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
        setTimeout(() => answerRef.current?.focus(), 50)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load card.')
    }
  }, [courseId])

  useEffect(() => {
    async function init() {
      try {
        const q = await getReviewQueue(courseId)
        setQueue(q)
        setSessionTotal(q.due_now)
        if (q.due_now === 0) {
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
      if (result.verdict === 'correct') setCorrect((c) => c + 1)
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
    setExitDir(rating <= 2 ? -1 : 1)
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

  const handleGradeRef = useRef(handleGrade)
  useLayoutEffect(() => {
    handleGradeRef.current = handleGrade
  })

  useEffect(() => {
    if (phase !== 'feedback') return
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLElement && e.target.closest('input, textarea, [contenteditable]')) {
        return
      }
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const rating = parseInt(e.key, 10)
      if (rating >= 1 && rating <= 4 && !grading) handleGradeRef.current(rating)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [phase, grading])

  const backLink = courseId ? `/courses/${courseId}` : '/courses'

  if (error) {
    return <ErrorState message={error} backTo={backLink} backLabel="Back to course" />
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Skeleton width="10rem" />
        <Skeleton variant="block" height="18rem" />
      </div>
    )
  }

  if (phase === 'empty') {
    return (
      <div className="mx-auto max-w-2xl">
        <h1 className="sr-only">Review</h1>
        <Card padding="none">
          <EmptyState
            icon={CalendarCheck}
            title="Nothing due right now"
            description="FSRS schedules each card for the moment just before you'd forget it. Come back when the next one is due."
            action={<ButtonLink to={backLink}>Back to course</ButtonLink>}
          />
        </Card>
      </div>
    )
  }

  if (phase === 'done') {
    const accuracy = graded > 0 ? Math.round((correct / graded) * 100) : 0
    return (
      <div className="mx-auto max-w-2xl">
        <h1 className="sr-only">Review complete</h1>
        <Card padding="lg" className="relative overflow-hidden text-center">
          <Confetti />
          <motion.div
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={springMomentum}
            className="relative flex justify-center"
          >
            <IconBadge icon={Trophy} tone="success" size="xl" />
          </motion.div>
          <p className="text-title-lg text-fg mt-5">Session complete</p>
          <p className="text-body text-fg-muted mt-2">
            {graded} card{graded === 1 ? '' : 's'} reviewed
            {graded > 0 && <> · {accuracy}% recalled correctly</>}
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <ButtonLink to={backLink}>Back to course</ButtonLink>
            <ButtonLink to="/courses" variant="secondary">
              Review another course
            </ButtonLink>
          </div>
        </Card>
      </div>
    )
  }

  if (!card) return null

  const isFillBlank = card.question_type === 'fill_blank'
  const progress = sessionTotal > 0 ? graded / sessionTotal : 0

  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,42rem)_18rem] xl:justify-center">
      <div className="min-w-0">
        <div className="mb-6">
          <div className="mb-2 flex items-baseline justify-between gap-3">
            <h1 className="text-title text-fg">Review</h1>
            <span className="text-caption text-fg-subtle tabular-nums">
              {graded} / {sessionTotal}
            </span>
          </div>
          <ProgressBar value={progress} size="sm" label="Session progress" hideLabel />
        </div>

        <div className="relative">
          {/* A second card peeking behind makes the stack legible. */}
          <div
            aria-hidden="true"
            className="border-border bg-surface absolute inset-x-3 -bottom-2 h-full rounded-lg border opacity-40"
          />

          <AnimatePresence mode="popLayout" initial={false}>
            <motion.div
              key={card.id}
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1, transition: springDefault }}
              exit={{
                opacity: 0,
                x: exitDir * 48,
                rotate: exitDir * 2,
                scale: 0.96,
                transition: springMomentum,
              }}
              className="relative"
            >
              <Card padding="lg" elevation={3}>
                {isFillBlank && card.code_snippet && (
                  <div className="mb-4">
                    <CodeBlock code={card.code_snippet} language="python" />
                  </div>
                )}

                <div className="mb-5 flex items-start gap-3">
                  {isFillBlank && (
                    <Badge tone="info" size="sm" className="mt-1 shrink-0">
                      Fill blank
                    </Badge>
                  )}
                  <p className="text-body-lg text-fg text-pretty">{card.question_text}</p>
                </div>

                {phase === 'answering' ? (
                  <div className="space-y-3">
                    {isFillBlank ? (
                      <Input
                        value={userAnswer}
                        onChange={(e) => setUserAnswer(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleCheckAnswer()}
                        placeholder="Your answer…"
                        aria-label="Your answer"
                        className="font-mono"
                      />
                    ) : (
                      <Textarea
                        ref={answerRef}
                        value={userAnswer}
                        onChange={(e) => setUserAnswer(e.target.value)}
                        rows={3}
                        placeholder="Recall it in your own words…"
                        aria-label="Your answer"
                      />
                    )}
                    <Button
                      onClick={handleCheckAnswer}
                      loading={checking}
                      disabled={!userAnswer.trim()}
                    >
                      Check answer
                    </Button>
                  </div>
                ) : (
                  feedback && (
                    <div className="space-y-4">
                      <VerdictPanel
                        verdict={feedback.verdict}
                        score={feedback.score}
                        explanation={feedback.explanation}
                        signalUsed={feedback.signal_used}
                      />

                      <div className="border-hairline bg-canvas-elevated rounded-md border p-4">
                        <p className="text-eyebrow text-fg-subtle mb-1.5 uppercase">
                          Reference answer
                        </p>
                        <p className="text-callout text-fg-muted">
                          {card.question_reference_answer}
                        </p>
                      </div>

                      <div>
                        <p className="text-caption text-fg-subtle mb-2">
                          How well did you recall it?
                        </p>
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                          {RATINGS.map(({ label, value, icon: Icon, cls }) => (
                            <motion.button
                              key={value}
                              whileTap={{ scale: 0.96 }}
                              transition={springDefault}
                              onClick={() => handleGrade(value)}
                              disabled={grading}
                              className={cn(
                                'flex min-h-16 flex-col items-center justify-center gap-1 rounded-md border transition-colors duration-[--duration-fast] disabled:opacity-50',
                                cls,
                              )}
                            >
                              <Icon size={16} aria-hidden="true" />
                              <span className="text-callout font-medium">{label}</span>
                              <kbd className="text-eyebrow text-fg-faint">{value}</kbd>
                            </motion.button>
                          ))}
                        </div>
                      </div>
                    </div>
                  )
                )}
              </Card>
            </motion.div>
          </AnimatePresence>
        </div>

        <div className="mt-6 flex justify-center">
          <ButtonLink to={backLink} variant="ghost" size="sm" icon={X}>
            End session
          </ButtonLink>
        </div>
      </div>

      <aside className="hidden xl:sticky xl:top-20 xl:block xl:self-start">
        <ReviewCalendar courseId={courseId} queue={queue} />
      </aside>
    </div>
  )
}
