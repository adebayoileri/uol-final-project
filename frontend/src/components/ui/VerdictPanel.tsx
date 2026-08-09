import { motion } from 'motion/react'
import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'
import { cn } from '../../lib/cn'
import { springDefault } from '../../motion/springs'
import type { AnswerResponse } from '../../api'

type Level = 'correct' | 'partial' | 'incorrect'

const STYLES: Record<Level, { wrap: string; icon: typeof CheckCircle2; text: string; label: string }> =
  {
    correct: {
      wrap: 'border-success/40 bg-success/10',
      icon: CheckCircle2,
      text: 'text-success',
      label: 'Correct',
    },
    partial: {
      wrap: 'border-warn/40 bg-warn/10',
      icon: AlertTriangle,
      text: 'text-warn',
      label: 'Partially correct',
    },
    incorrect: {
      wrap: 'border-danger/40 bg-danger/10',
      icon: XCircle,
      text: 'text-danger',
      label: 'Not quite',
    },
  }

const SIGNAL_LABEL: Record<AnswerResponse['signal_used'], string> = {
  embedding: 'Graded by embedding similarity',
  'embedding+llm': 'Graded by embedding similarity, confirmed by the model',
  llm: 'Graded by the model',
}

interface VerdictPanelProps {
  verdict: AnswerResponse['verdict']
  score: number
  explanation?: string
  signalUsed?: AnswerResponse['signal_used']
  className?: string
}

export default function VerdictPanel({
  verdict,
  score,
  explanation,
  signalUsed,
  className,
}: VerdictPanelProps) {
  const level: Level = verdict === 'correct' ? 'correct' : score >= 0.5 ? 'partial' : 'incorrect'
  const s = STYLES[level]
  const Icon = s.icon
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={springDefault}
      role="status"
      className={cn('rounded-md border p-4', s.wrap, className)}
    >
      <div className="flex items-start gap-3">
        <Icon size={18} className={cn('mt-0.5 shrink-0', s.text)} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <p className={cn('text-callout font-medium', s.text)}>{s.label}</p>
            <span className={cn('text-caption tabular-nums shrink-0', s.text, 'opacity-80')}>
              {pct}%
            </span>
          </div>
          {explanation && <p className="text-callout text-fg-muted mt-1.5">{explanation}</p>}
          {signalUsed && (
            <p className="text-caption text-fg-faint mt-2">{SIGNAL_LABEL[signalUsed]}</p>
          )}
        </div>
      </div>
    </motion.div>
  )
}
