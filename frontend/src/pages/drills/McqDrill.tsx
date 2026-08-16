import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import { getDrill, type McqItem } from '../../api'
import DrillShell from '../../components/practice/DrillShell'
import OptionPicker from '../../components/practice/OptionPicker'
import { Badge, Card, ErrorState, Skeleton } from '../../components/ui'
import { springDefault } from '../../motion/springs'

export default function McqDrill() {
  const { courseId } = useParams<{ courseId: string }>()
  const [items, setItems] = useState<McqItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [index, setIndex] = useState(0)
  const [picked, setPicked] = useState<number | null>(null)
  const [correct, setCorrect] = useState(0)
  const [finished, setFinished] = useState(false)

  const load = useCallback(() => {
    if (!courseId) return
    setItems(null)
    setError(null)
    setIndex(0)
    setPicked(null)
    setCorrect(0)
    setFinished(false)
    getDrill<McqItem>(courseId, 'mcq', 8)
      .then((r) => setItems(r.items))
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
  if (!items) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Skeleton width="10rem" />
        <Skeleton variant="block" height="16rem" />
      </div>
    )
  }

  const item = items[index]

  function handlePick(choice: number) {
    setPicked(choice)
    if (choice === item.answer_index) setCorrect((c) => c + 1)
  }

  function handleNext() {
    if (index + 1 >= items!.length) {
      setFinished(true)
      return
    }
    setIndex((i) => i + 1)
    setPicked(null)
  }

  return (
    <DrillShell
      courseId={courseId}
      kind="mcq"
      title="Multiple choice"
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
              <p className="text-body-lg text-fg mt-3 text-pretty">{item.prompt}</p>
              <p className="text-caption text-fg-subtle mt-2">Which concept is this?</p>
            </div>

            <OptionPicker
              options={item.options}
              answerIndex={item.answer_index}
              picked={picked}
              onPick={handlePick}
              onNext={handleNext}
              isLast={index + 1 >= items.length}
            />

            {picked !== null && item.example && (
              <div className="border-hairline bg-canvas-elevated rounded-md border p-3">
                <p className="text-eyebrow text-fg-subtle mb-1 uppercase">Example</p>
                <p className="text-caption text-fg-muted font-mono">{item.example}</p>
              </div>
            )}
          </Card>
        </motion.div>
      </AnimatePresence>
    </DrillShell>
  )
}
