import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronLeft, ChevronRight, Sparkles } from 'lucide-react'
import { answerQuestion, type AnswerResponse, type QuestionResponse } from '../../api'
import CodeBlock from '../CodeBlock'
import { Badge, Button, Card, Input, Textarea, VerdictPanel } from '../ui'
import { springDefault } from '../../motion/springs'
import { cn } from '../../lib/cn'

type Phase = 'answering' | 'feedback'

interface QuestionDeckProps {
  questions: QuestionResponse[]
  index: number
  onIndexChange: (next: number) => void
  onError: (message: string) => void
}

export default function QuestionDeck({
  questions,
  index,
  onIndexChange,
  onError,
}: QuestionDeckProps) {
  const [phase, setPhase] = useState<Phase>('answering')
  const [userAnswer, setUserAnswer] = useState('')
  const [checking, setChecking] = useState(false)
  const [feedback, setFeedback] = useState<AnswerResponse | null>(null)
  // Drives the slide direction, so forward and back mirror each other.
  const [direction, setDirection] = useState(1)

  const current = questions[index] ?? null
  if (!current) return null

  function move(to: number, dir: number) {
    setDirection(dir)
    onIndexChange(to)
    setPhase('answering')
    setUserAnswer('')
    setFeedback(null)
  }

  const goNext = () => index < questions.length - 1 && move(index + 1, 1)
  const goPrev = () => index > 0 && move(index - 1, -1)

  async function handleCheck() {
    if (!current || !userAnswer.trim()) return
    setChecking(true)
    try {
      const result = await answerQuestion(current.id, userAnswer)
      setFeedback(result)
      setPhase('feedback')
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Check failed.')
    } finally {
      setChecking(false)
    }
  }

  const isFillBlank = current.question_type === 'fill_blank'

  return (
    <Card padding="lg" elevation={2}>
      <div className="mb-5 flex items-center justify-between gap-4">
        {/* Step dots replace the bare "3 / 8" counter. */}
        <div className="flex items-center gap-1.5" role="tablist" aria-label="Questions">
          {questions.map((q, i) => (
            <button
              key={q.id}
              role="tab"
              aria-selected={i === index}
              aria-label={`Question ${i + 1}`}
              onClick={() => move(i, i > index ? 1 : -1)}
              className={cn(
                'h-1.5 rounded-full transition-all duration-[--duration-base]',
                i === index ? 'bg-brand-400 w-6' : 'bg-border hover:bg-border-strong w-1.5',
              )}
            />
          ))}
        </div>
        <span className="text-caption text-fg-subtle shrink-0 tabular-nums">
          {index + 1} of {questions.length}
        </span>
      </div>

      <AnimatePresence mode="wait" initial={false} custom={direction}>
        <motion.div
          key={current.id}
          custom={direction}
          initial={{ opacity: 0, x: direction * 24 }}
          animate={{ opacity: 1, x: 0, transition: springDefault }}
          exit={{ opacity: 0, x: direction * -24, transition: { duration: 0.12 } }}
        >
          {isFillBlank && current.code_snippet && (
            <div className="mb-4">
              <CodeBlock code={current.code_snippet} language="python" />
            </div>
          )}

          <div className="mb-4 flex items-start gap-3">
            {isFillBlank && (
              <Badge tone="info" size="sm" className="mt-1 shrink-0">
                Fill blank
              </Badge>
            )}
            <p className="text-body-lg text-fg text-pretty">{current.text}</p>
          </div>

          {phase === 'answering' ? (
            <div className="space-y-3">
              {isFillBlank ? (
                <Input
                  value={userAnswer}
                  onChange={(e) => setUserAnswer(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCheck()}
                  placeholder="Your answer…"
                  aria-label="Your answer"
                  className="font-mono"
                />
              ) : (
                <Textarea
                  value={userAnswer}
                  onChange={(e) => setUserAnswer(e.target.value)}
                  rows={3}
                  placeholder="Answer in your own words…"
                  aria-label="Your answer"
                />
              )}
              <Button onClick={handleCheck} loading={checking} disabled={!userAnswer.trim()}>
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
                  <p className="text-eyebrow text-fg-subtle mb-1.5 uppercase">Reference answer</p>
                  <p className="text-callout text-fg-muted">{current.reference_answer}</p>
                </div>
                {index < questions.length - 1 && (
                  <Button variant="secondary" icon={ChevronRight} iconPosition="right" onClick={goNext}>
                    Next question
                  </Button>
                )}
              </div>
            )
          )}
        </motion.div>
      </AnimatePresence>

      <div className="border-hairline mt-6 flex items-center justify-between gap-2 border-t pt-4">
        <Button
          variant="ghost"
          size="sm"
          icon={ChevronLeft}
          onClick={goPrev}
          disabled={index === 0}
        >
          Previous
        </Button>
        <Button
          variant="ghost"
          size="sm"
          icon={ChevronRight}
          iconPosition="right"
          onClick={goNext}
          disabled={index >= questions.length - 1}
        >
          Next
        </Button>
      </div>
    </Card>
  )
}

export function GenerateQuestionsPrompt({
  onGenerate,
  generating,
}: {
  onGenerate: () => void
  generating: boolean
}) {
  return (
    <Card padding="lg" className="text-center">
      <p className="text-callout text-fg-muted mx-auto max-w-sm">
        Generate practice questions for this lesson. Each one becomes a spaced-repetition card.
      </p>
      <Button icon={Sparkles} onClick={onGenerate} loading={generating} className="mt-4">
        Generate questions
      </Button>
    </Card>
  )
}
