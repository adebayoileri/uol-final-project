import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { motion } from 'motion/react'
import { Ear, Mic, RotateCcw, Square } from 'lucide-react'
import {
  checkPronunciation,
  getCourseDrills,
  getDrill,
  type PronounceItem,
  type PronunciationCheckResponse,
  type WordDiffItem,
} from '../api'
import LevelMeter from '../components/practice/LevelMeter'
import {
  Badge,
  Card,
  ErrorState,
  Field,
  IconBadge,
  Input,
  PageHeader,
  Select,
  Spinner,
} from '../components/ui'
import { springDefault } from '../motion/springs'
import { cn } from '../lib/cn'

type DrillState = 'idle' | 'recording' | 'processing' | 'result' | 'error'

const LEGEND = [
  { cls: 'bg-success', label: 'Correct' },
  { cls: 'bg-danger', label: 'Missing' },
  { cls: 'bg-warn', label: 'Substituted' },
  { cls: 'bg-fg-faint', label: 'Extra' },
]

function WordToken({ item }: { item: WordDiffItem }) {
  if (item.op === 'match') return <span className="text-success">{item.expected}</span>
  if (item.op === 'missing') {
    return <span className="bg-danger/15 text-danger rounded px-1.5">[{item.expected}]</span>
  }
  if (item.op === 'substituted') {
    return <span className="text-warn decoration-warn underline underline-offset-4">{item.actual}</span>
  }
  return <span className="text-fg-faint line-through">{item.actual}</span>
}

function PronunciationDrill() {
  const { courseId } = useParams<{ courseId?: string }>()

  // Phrases come from the course's own concepts. They used to be five
  // hardcoded Spanish strings shown to every course, chess included.
  const [items, setItems] = useState<PronounceItem[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [language, setLanguage] = useState('es')
  const [phrase, setPhrase] = useState('')
  const [custom, setCustom] = useState('')
  const [useCustom, setUseCustom] = useState(false)

  const [state, setState] = useState<DrillState>('idle')
  const [result, setResult] = useState<PronunciationCheckResponse | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [elapsed, setElapsed] = useState(0)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])

  const activePhrase = useCustom ? custom.trim() : phrase

  const loadPhrases = useCallback(() => {
    if (!courseId) return
    setItems(null)
    setLoadError(null)
    Promise.all([
      getDrill<PronounceItem>(courseId, 'pronounce', 12),
      getCourseDrills(courseId).catch(() => null),
    ])
      .then(([drill, availability]) => {
        setItems(drill.items)
        if (drill.items[0]) setPhrase(drill.items[0].phrase)
        if (availability?.target_language) setLanguage(availability.target_language)
      })
      .catch((err: Error) => setLoadError(err.message))
  }, [courseId])

  useEffect(loadPhrases, [loadPhrases])

  useEffect(() => {
    if (state !== 'recording') {
      setElapsed(0)
      return
    }
    const started = Date.now()
    const id = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 250)
    return () => window.clearInterval(id)
  }, [state])

  async function startRecording() {
    setResult(null)
    setErrorMsg(null)
    chunksRef.current = []

    let mediaStream: MediaStream
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setErrorMsg(
        'Microphone access was denied. Allow microphone access in your browser settings and try again.',
      )
      setState('error')
      return
    }

    setStream(mediaStream)
    const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4'
    const recorder = new MediaRecorder(mediaStream, { mimeType })
    mediaRecorderRef.current = recorder

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data)
    }

    recorder.onstop = async () => {
      mediaStream.getTracks().forEach((t) => t.stop())
      setStream(null)
      const blob = new Blob(chunksRef.current, { type: mimeType })
      setState('processing')
      try {
        const res = await checkPronunciation(blob, activePhrase, language)
        setResult(res)
        setState('result')
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : 'Pronunciation check failed.')
        setState('error')
      }
    }

    recorder.start()
    setState('recording')
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop()
  }

  function reset() {
    setState('idle')
    setResult(null)
    setErrorMsg(null)
  }

  const isRecording = state === 'recording'
  const isProcessing = state === 'processing'
  const accuracyPct = result ? Math.round(result.accuracy * 100) : 0
  const accuracyTone = accuracyPct >= 80 ? 'success' : accuracyPct >= 50 ? 'warn' : 'danger'

  if (loadError) {
    return (
      <ErrorState
        title="No phrases to practise"
        message={loadError}
        onRetry={loadPhrases}
        backTo={courseId ? `/practice/${courseId}` : '/practice'}
        backLabel="Other drills"
      />
    )
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Practice"
        title="Pronunciation drill"
        description="Say a phrase out loud. Whisper transcribes it and you get word-by-word feedback."
        backTo={courseId ? `/practice/${courseId}` : '/practice'}
        backLabel={courseId ? 'Other drills' : 'Practice'}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card padding="lg" className="space-y-5">
          <Field label="Phrase">
            {(p) => (
              <Select
                value={useCustom ? '__custom__' : phrase}
                onChange={(e) => {
                  if (e.target.value === '__custom__') setUseCustom(true)
                  else {
                    setUseCustom(false)
                    setPhrase(e.target.value)
                  }
                }}
                {...p}
              >
                {(items ?? []).map((item) => (
                  <option key={item.id} value={item.phrase}>
                    {item.phrase}
                  </option>
                ))}
                <option value="__custom__">Custom phrase…</option>
              </Select>
            )}
          </Field>

          {useCustom && (
            <Field label="Your phrase">
              {(p) => (
                <Input
                  value={custom}
                  onChange={(e) => setCustom(e.target.value)}
                  placeholder="Type a phrase to practise…"
                  {...p}
                />
              )}
            </Field>
          )}

          {/* The thing you read aloud should be the biggest text on the page. */}
          <div className="border-hairline bg-canvas-elevated rounded-md border px-5 py-4">
            <p className="text-eyebrow text-fg-subtle mb-1.5 uppercase">Say this</p>
            <p className="text-title text-fg text-balance">
              {activePhrase || <span className="text-fg-faint">Enter a phrase…</span>}
            </p>
          </div>

          <div className="flex flex-col items-center gap-3 pt-2">
            <div className="relative">
              {isRecording && (
                <span className="animate-pulse-ring absolute inset-0 rounded-full" aria-hidden="true" />
              )}
              <motion.button
                whileTap={{ scale: 0.94 }}
                transition={springDefault}
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isProcessing || !activePhrase}
                aria-label={isRecording ? 'Stop recording' : 'Start recording'}
                className={cn(
                  'relative grid size-16 place-items-center rounded-full text-on-brand transition-colors disabled:opacity-50',
                  isRecording ? 'bg-danger' : 'bg-brand-500 hover:bg-brand-400',
                )}
              >
                {isProcessing ? (
                  <Spinner size="lg" />
                ) : isRecording ? (
                  <Square size={20} fill="currentColor" />
                ) : (
                  <Mic size={22} />
                )}
              </motion.button>
            </div>

            {isRecording ? (
              <>
                <LevelMeter stream={stream} />
                <p className="text-caption text-fg-subtle tabular-nums" aria-live="polite">
                  Recording · {Math.floor(elapsed / 60)}:
                  {String(elapsed % 60).padStart(2, '0')}
                </p>
              </>
            ) : (
              <p className="text-caption text-fg-subtle">
                {isProcessing ? 'Transcribing…' : 'Tap to record'}
              </p>
            )}

            {state === 'result' && (
              <button
                onClick={reset}
                className="text-callout text-brand-300 hover:text-brand-200 inline-flex min-h-11 items-center gap-1.5"
              >
                <RotateCcw size={14} aria-hidden="true" />
                Try again
              </button>
            )}
          </div>
        </Card>

        <div className="space-y-4">
          {errorMsg && <ErrorState inline message={errorMsg} onRetry={reset} />}

          {result && (
            <Card padding="lg" className="space-y-5">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-headline text-fg">Word-by-word</h2>
                <Badge tone={accuracyTone}>{accuracyPct}% accurate</Badge>
              </div>

              <motion.p className="text-body-lg flex flex-wrap gap-x-2 gap-y-1.5">
                {result.diff.map((item, i) => (
                  <motion.span
                    key={i}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ ...springDefault, delay: i * 0.025 }}
                  >
                    <WordToken item={item} />
                  </motion.span>
                ))}
              </motion.p>

              <div className="border-hairline border-t pt-4">
                <h3 className="text-eyebrow text-fg-subtle mb-1.5 flex items-center gap-2 uppercase">
                  <IconBadge icon={Ear} tone="info" size="sm" />
                  What the model heard
                </h3>
                <p className="text-callout text-fg-muted mt-2">
                  {result.transcribed_text || (
                    <span className="text-fg-faint italic">(nothing)</span>
                  )}
                </p>
              </div>

              <div className="text-caption text-fg-subtle flex flex-wrap gap-4">
                {LEGEND.map(({ cls, label }) => (
                  <span key={label} className="inline-flex items-center gap-1.5">
                    <span className={cn('size-2.5 rounded-sm', cls)} aria-hidden="true" />
                    {label}
                  </span>
                ))}
              </div>
            </Card>
          )}

          {!result && !errorMsg && (
            <Card padding="lg" className="text-center">
              <IconBadge icon={Mic} tone="neutral" size="lg" className="mx-auto mb-3" />
              <p className="text-callout text-fg-muted">
                Your feedback appears here once you've recorded a phrase.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

export default PronunciationDrill
