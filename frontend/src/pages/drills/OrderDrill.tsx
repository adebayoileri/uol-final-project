import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowDown, ArrowUp, Check, X } from 'lucide-react'
import { getDrill, type OrderItem } from '../../api'
import DrillShell from '../../components/practice/DrillShell'
import { Badge, Button, Card, ErrorState, Skeleton } from '../../components/ui'
import { springDefault } from '../../motion/springs'
import { cn } from '../../lib/cn'

export default function OrderDrill() {
  const { courseId } = useParams<{ courseId: string }>()
  const [items, setItems] = useState<OrderItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [index, setIndex] = useState(0)
  /** Display indices in the learner's current arrangement. */
  const [arrangement, setArrangement] = useState<number[]>([])
  const [checked, setChecked] = useState(false)
  const [correct, setCorrect] = useState(0)
  const [finished, setFinished] = useState(false)

  const load = useCallback(() => {
    if (!courseId) return
    setItems(null)
    setError(null)
    setIndex(0)
    setChecked(false)
    setCorrect(0)
    setFinished(false)
    getDrill<OrderItem>(courseId, 'order', 5)
      .then((r) => {
        setItems(r.items)
        if (r.items[0]) setArrangement(r.items[0].steps.map((_, i) => i))
      })
      .catch((err: Error) => setError(err.message))
  }, [courseId])

  useEffect(load, [load])

  if (!courseId) return <ErrorState message="No course selected." backTo="/practice" />
  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={load}
        backTo={`/practice/${courseId}`}
        backLabel="Other drills"
      />
    )
  }
  if (!items || !items[index]) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Skeleton width="10rem" />
        <Skeleton variant="block" height="20rem" />
      </div>
    )
  }

  const item = items[index]
  const isRight = arrangement.join(',') === item.correct_order.join(',')

  // Move-up/down rather than drag-and-drop: draggable lists are a keyboard
  // dead end and awkward on touch.
  function move(from: number, to: number) {
    if (checked || to < 0 || to >= arrangement.length) return
    const next = arrangement.slice()
    ;[next[from], next[to]] = [next[to], next[from]]
    setArrangement(next)
  }

  function handleCheck() {
    setChecked(true)
    if (isRight) setCorrect((c) => c + 1)
  }

  function handleNext() {
    if (index + 1 >= items!.length) {
      setFinished(true)
      return
    }
    const next = index + 1
    setIndex(next)
    setArrangement(items![next].steps.map((_, i) => i))
    setChecked(false)
  }

  return (
    <DrillShell
      courseId={courseId}
      kind="order"
      title="Step order"
      index={index}
      total={items.length}
      correct={correct}
      finished={finished}
      onRestart={load}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={item.id}
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0, transition: springDefault }}
          exit={{ opacity: 0, x: -16, transition: { duration: 0.12 } }}
        >
          <Card padding="lg" elevation={2} className="space-y-5">
            <div>
              <Badge tone="neutral" size="sm">
                {item.lesson_title}
              </Badge>
              <p className="text-body-lg text-fg mt-3">Put these steps back in order.</p>
            </div>

            <ol className="space-y-2">
              {arrangement.map((stepIdx, position) => {
                const rightHere = checked && item.correct_order[position] === stepIdx
                return (
                  <motion.li
                    key={stepIdx}
                    layout
                    transition={springDefault}
                    className={cn(
                      'flex items-start gap-3 rounded-md border px-3 py-2.5',
                      !checked && 'border-border bg-surface',
                      rightHere && 'border-success/50 bg-success/10',
                      checked && !rightHere && 'border-danger/50 bg-danger/10',
                    )}
                  >
                    <span className="text-caption text-fg-faint mt-0.5 w-5 shrink-0 tabular-nums">
                      {position + 1}
                    </span>
                    <span className="text-callout text-fg-muted flex-1">{item.steps[stepIdx]}</span>
                    {checked ? (
                      rightHere ? (
                        <Check size={15} className="text-success mt-0.5 shrink-0" aria-hidden="true" />
                      ) : (
                        <X size={15} className="text-danger mt-0.5 shrink-0" aria-hidden="true" />
                      )
                    ) : (
                      <span className="flex shrink-0 gap-1">
                        <button
                          onClick={() => move(position, position - 1)}
                          disabled={position === 0}
                          aria-label={`Move step ${position + 1} up`}
                          className="text-fg-faint hover:text-fg rounded p-1 transition-colors disabled:opacity-30"
                        >
                          <ArrowUp size={14} />
                        </button>
                        <button
                          onClick={() => move(position, position + 1)}
                          disabled={position === arrangement.length - 1}
                          aria-label={`Move step ${position + 1} down`}
                          className="text-fg-faint hover:text-fg rounded p-1 transition-colors disabled:opacity-30"
                        >
                          <ArrowDown size={14} />
                        </button>
                      </span>
                    )}
                  </motion.li>
                )
              })}
            </ol>

            {checked ? (
              <div className="space-y-3">
                <p className={cn('text-callout', isRight ? 'text-success' : 'text-danger')}>
                  {isRight ? 'Correct order.' : 'Not quite — the correct order is highlighted.'}
                </p>
                <Button onClick={handleNext} fullWidth>
                  {index + 1 >= items.length ? 'Finish' : 'Next'}
                </Button>
              </div>
            ) : (
              <Button onClick={handleCheck} fullWidth>
                Check order
              </Button>
            )}
          </Card>
        </motion.div>
      </AnimatePresence>
    </DrillShell>
  )
}
