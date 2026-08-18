import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import { Play, Volume2 } from 'lucide-react'
import { getDrill, type ListenItem } from '../../api'
import { API_URL } from '../../config'
import DrillShell from '../../components/practice/DrillShell'
import OptionPicker from '../../components/practice/OptionPicker'
import { Badge, Button, Card, ErrorState, IconBadge, Skeleton } from '../../components/ui'
import { springDefault } from '../../motion/springs'

export default function ListenDrill() {
  const { courseId } = useParams<{ courseId: string }>()
  const [items, setItems] = useState<ListenItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [index, setIndex] = useState(0)
  const [picked, setPicked] = useState<number | null>(null)
  const [correct, setCorrect] = useState(0)
  const [finished, setFinished] = useState(false)
  const [playing, setPlaying] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const load = useCallback(() => {
    if (!courseId) return
    setItems(null)
    setError(null)
    setIndex(0)
    setPicked(null)
    setCorrect(0)
    setFinished(false)
    getDrill<ListenItem>(courseId, 'listen', 8)
      .then((r) => setItems(r.items))
      .catch((err: Error) => setError(err.message))
  }, [courseId])

  useEffect(load, [load])

  /**
   * Stop the clip whenever it stops being the question.
   *
   * The previous cleanup ran on unmount only, but the score screen renders
   * inside this same component — so finishing the drill did not unmount it and
   * the last clip carried on playing over "Listening complete". `load` also
   * clears `finished`, so this covers restart as well.
   */
  useEffect(() => {
    if (!finished) return
    audioRef.current?.pause()
    setPlaying(false)
  }, [finished])

  useEffect(() => () => audioRef.current?.pause(), [])

  const item = items?.[index]

  const play = useCallback(() => {
    if (!item) return
    audioRef.current?.pause()
    const audio = new Audio(`${API_URL}${item.audio_url}`)
    audioRef.current = audio
    audio.addEventListener('ended', () => setPlaying(false))
    audio.addEventListener('error', () => setPlaying(false))
    setPlaying(true)
    void audio.play().catch(() => setPlaying(false))
  }, [item])

  // Play automatically on arrival — the audio IS the question.
  useEffect(() => {
    if (item) play()
  }, [item, play])

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
  if (!items || !item) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Skeleton width="10rem" />
        <Skeleton variant="block" height="16rem" />
      </div>
    )
  }

  function handlePick(choice: number) {
    setPicked(choice)
    if (choice === item!.answer_index) setCorrect((c) => c + 1)
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
      kind="listen"
      title="Listening"
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
              {/* The definition is never sent to the client — reading it
                  instead of hearing it would defeat the drill. */}
              <div className="mt-4 flex flex-col items-center gap-3 py-4">
                <motion.div
                  animate={playing ? { scale: [1, 1.06, 1] } : { scale: 1 }}
                  transition={{ duration: 1.2, repeat: playing ? Infinity : 0 }}
                >
                  <IconBadge icon={Volume2} tone="success" size="xl" />
                </motion.div>
                <Button variant="secondary" icon={Play} onClick={play} size="sm">
                  {playing ? 'Playing…' : 'Replay'}
                </Button>
                <p className="text-caption text-fg-subtle">Which concept was described?</p>
              </div>
            </div>

            <OptionPicker
              options={item.options}
              answerIndex={item.answer_index}
              picked={picked}
              onPick={handlePick}
              onNext={handleNext}
              isLast={index + 1 >= items.length}
            />
          </Card>
        </motion.div>
      </AnimatePresence>
    </DrillShell>
  )
}
