import { motion } from 'motion/react'
import { Check, X } from 'lucide-react'
import { Button } from '../ui'
import { springDefault } from '../../motion/springs'
import { cn } from '../../lib/cn'

interface OptionPickerProps {
  options: string[]
  answerIndex: number
  /** null until the learner commits. */
  picked: number | null
  onPick: (index: number) => void
  onNext: () => void
  isLast: boolean
}

/**
 * Shared by the multiple-choice and listening drills — the only difference
 * between them is whether the prompt is read or heard.
 */
export default function OptionPicker({
  options,
  answerIndex,
  picked,
  onPick,
  onNext,
  isLast,
}: OptionPickerProps) {
  const answered = picked !== null

  return (
    <div className="space-y-4">
      <ul className="space-y-2">
        {options.map((option, i) => {
          const isAnswer = i === answerIndex
          const isPicked = i === picked
          const state = !answered
            ? 'idle'
            : isAnswer
              ? 'correct'
              : isPicked
                ? 'wrong'
                : 'muted'

          return (
            <li key={option}>
              <motion.button
                whileTap={answered ? undefined : { scale: 0.99 }}
                transition={springDefault}
                onClick={() => !answered && onPick(i)}
                disabled={answered}
                className={cn(
                  'text-body flex w-full items-center gap-3 rounded-md border px-4 py-3 text-left transition-colors duration-[--duration-fast]',
                  state === 'idle' &&
                    'border-border bg-surface hover:border-border-strong hover:bg-surface-raised text-fg',
                  state === 'correct' && 'border-success/50 bg-success/10 text-success',
                  state === 'wrong' && 'border-danger/50 bg-danger/10 text-danger',
                  state === 'muted' && 'border-border bg-surface text-fg-faint',
                )}
              >
                <span className="flex-1">{option}</span>
                {state === 'correct' && <Check size={16} aria-hidden="true" />}
                {state === 'wrong' && <X size={16} aria-hidden="true" />}
              </motion.button>
            </li>
          )
        })}
      </ul>

      {answered && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={springDefault}
        >
          <Button onClick={onNext} fullWidth>
            {isLast ? 'Finish' : 'Next'}
          </Button>
        </motion.div>
      )}
    </div>
  )
}
