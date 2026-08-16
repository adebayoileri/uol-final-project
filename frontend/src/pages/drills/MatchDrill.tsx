import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { motion } from 'motion/react'
import { Check } from 'lucide-react'
import { getDrill, type MatchItem } from '../../api'
import DrillShell from '../../components/practice/DrillShell'
import { Card, ErrorState, Skeleton } from '../../components/ui'
import { springDefault } from '../../motion/springs'
import { cn } from '../../lib/cn'

function shuffled<T>(items: T[]): T[] {
  const out = items.slice()
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

export default function MatchDrill() {
  const { courseId } = useParams<{ courseId: string }>()
  const [items, setItems] = useState<MatchItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [matched, setMatched] = useState<Set<string>>(new Set())
  const [wrongPair, setWrongPair] = useState<string | null>(null)
  const [attempts, setAttempts] = useState(0)
  const [finished, setFinished] = useState(false)

  const load = useCallback(() => {
    if (!courseId) return
    setItems(null)
    setError(null)
    setSelectedName(null)
    setMatched(new Set())
    setWrongPair(null)
    setAttempts(0)
    setFinished(false)
    getDrill<MatchItem>(courseId, 'match', 6)
      .then((r) => setItems(r.items))
      .catch((err: Error) => setError(err.message))
  }, [courseId])

  useEffect(load, [load])

  // The right column is shuffled independently, or the pairing is trivial.
  const definitions = useMemo(() => (items ? shuffled(items) : []), [items])

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
        <Skeleton variant="block" height="20rem" />
      </div>
    )
  }

  function handleDefinition(item: MatchItem) {
    if (!selectedName || matched.has(item.id)) return
    setAttempts((a) => a + 1)
    if (item.name === selectedName) {
      const next = new Set(matched).add(item.id)
      setMatched(next)
      setSelectedName(null)
      if (next.size === items!.length) setFinished(true)
    } else {
      setWrongPair(item.id)
      window.setTimeout(() => setWrongPair(null), 500)
      setSelectedName(null)
    }
  }

  // Score is pairs found relative to attempts taken — a perfect run is one
  // attempt per pair.
  const correct = matched.size
  const total = items.length

  return (
    <DrillShell
      courseId={courseId}
      kind="match"
      title="Concept match"
      index={matched.size}
      total={total}
      correct={correct}
      finished={finished}
      onRestart={load}
    >
      <Card padding="lg" elevation={2}>
        <p className="text-caption text-fg-subtle mb-4">
          Pick a concept, then its definition. {attempts > 0 && `${attempts} attempt${attempts === 1 ? '' : 's'}.`}
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2">
            {items.map((item) => {
              const done = matched.has(item.id)
              const active = selectedName === item.name
              return (
                <motion.button
                  key={item.id}
                  whileTap={done ? undefined : { scale: 0.98 }}
                  transition={springDefault}
                  disabled={done}
                  onClick={() => setSelectedName(item.name)}
                  className={cn(
                    'text-callout flex w-full items-center gap-2 rounded-md border px-3 py-2.5 text-left transition-colors duration-[--duration-fast]',
                    done && 'border-success/50 bg-success/10 text-success',
                    !done && active && 'border-brand-500 bg-brand-500/10 text-fg',
                    !done && !active && 'border-border bg-surface hover:border-border-strong text-fg',
                  )}
                >
                  <span className="flex-1">{item.name}</span>
                  {done && <Check size={14} aria-hidden="true" />}
                </motion.button>
              )
            })}
          </div>

          <div className="space-y-2">
            {definitions.map((item) => {
              const done = matched.has(item.id)
              const wrong = wrongPair === item.id
              return (
                <motion.button
                  key={item.id}
                  animate={wrong ? { x: [0, -6, 6, -4, 0] } : { x: 0 }}
                  transition={{ duration: 0.35 }}
                  disabled={done}
                  onClick={() => handleDefinition(item)}
                  className={cn(
                    'text-caption w-full rounded-md border px-3 py-2.5 text-left transition-colors duration-[--duration-fast]',
                    done && 'border-success/50 bg-success/10 text-success',
                    wrong && 'border-danger/50 bg-danger/10 text-danger',
                    !done && !wrong && 'border-border bg-surface hover:border-border-strong text-fg-muted',
                    !selectedName && !done && 'opacity-70',
                  )}
                >
                  {item.definition}
                </motion.button>
              )
            })}
          </div>
        </div>
      </Card>
    </DrillShell>
  )
}
