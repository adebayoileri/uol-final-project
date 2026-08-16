import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import { ArrowLeft, RotateCcw, Trophy } from 'lucide-react'
import { completeDrill, type DrillKind } from '../../api'
import Confetti from '../review/Confetti'
import { Button, ButtonLink, Card, IconBadge, ProgressBar } from '../ui'
import { springMomentum } from '../../motion/springs'

interface DrillShellProps {
  courseId: string
  kind: DrillKind
  title: string
  /** 0-based index of the current item. */
  index: number
  total: number
  correct: number
  finished: boolean
  onRestart: () => void
  children: React.ReactNode
}

/**
 * Chrome shared by every drill: progress, running score, and the completion
 * screen. Keeps each drill to its own interaction and nothing else.
 */
export default function DrillShell({
  courseId,
  kind,
  title,
  index,
  total,
  correct,
  finished,
  onRestart,
  children,
}: DrillShellProps) {
  const [recorded, setRecorded] = useState(false)

  useEffect(() => {
    if (!finished || recorded) return
    setRecorded(true)
    // Best-effort: a failed event must not disturb the score screen.
    completeDrill(courseId, kind, correct, total).catch(() => {})
  }, [finished, recorded, courseId, kind, correct, total])

  useEffect(() => {
    if (!finished) setRecorded(false)
  }, [finished])

  if (finished) {
    const pct = total > 0 ? Math.round((correct / total) * 100) : 0
    return (
      <div className="mx-auto max-w-2xl">
        <Card padding="lg" className="relative overflow-hidden text-center">
          <Confetti />
          <motion.div
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={springMomentum}
            className="relative flex justify-center"
          >
            <IconBadge icon={Trophy} tone={pct >= 70 ? 'success' : 'warn'} size="xl" />
          </motion.div>
          <p className="text-title-lg text-fg mt-5">{title} complete</p>
          <p className="text-body text-fg-muted mt-2 tabular-nums">
            {correct} of {total} correct · {pct}%
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Button icon={RotateCcw} onClick={onRestart}>
              Try again
            </Button>
            <ButtonLink to={`/practice/${courseId}`} variant="secondary">
              Other drills
            </ButtonLink>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Link
          to={`/practice/${courseId}`}
          className="text-callout text-fg-subtle hover:text-fg -ml-2 mb-3 inline-flex min-h-11 items-center gap-1.5 rounded-md px-2 transition-colors"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          Drills
        </Link>
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <h1 className="text-title text-fg">{title}</h1>
          <span className="text-caption text-fg-subtle tabular-nums">
            {Math.min(index + 1, total)} / {total}
          </span>
        </div>
        <ProgressBar
          value={total > 0 ? index / total : 0}
          size="sm"
          label="Drill progress"
          hideLabel
        />
      </div>
      {children}
    </div>
  )
}
