import { useRef, useState } from 'react'
import { checkPronunciation, type PronunciationCheckResponse, type WordDiffItem } from '../api'

const PRESET_PHRASES = [
  'Hola me llamo Juan',
  'Buenos días cómo estás',
  'Me gustaría un café por favor',
  'Dónde está el baño',
  'Hablas inglés',
]

type DrillState = 'idle' | 'recording' | 'processing' | 'result' | 'error'

function WordToken({ item }: { item: WordDiffItem }) {
  if (item.op === 'match') {
    return <span className="text-green-400">{item.expected}</span>
  }
  if (item.op === 'missing') {
    return (
      <span className="rounded bg-red-900/40 px-1 text-red-400">
        [{item.expected}]
      </span>
    )
  }
  if (item.op === 'substituted') {
    return (
      <span className="underline decoration-yellow-500 text-yellow-400">
        {item.actual}
      </span>
    )
  }
  // extra
  return (
    <span className="line-through text-gray-500">
      {item.actual}
    </span>
  )
}

function AccuracyBadge({ accuracy }: { accuracy: number }) {
  const pct = Math.round(accuracy * 100)
  const colour =
    pct >= 80 ? 'bg-green-900/40 text-green-400 border-green-800'
    : pct >= 50 ? 'bg-yellow-900/40 text-yellow-400 border-yellow-800'
    : 'bg-red-900/40 text-red-400 border-red-800'
  return (
    <span className={`rounded-lg border px-3 py-1 text-sm font-semibold ${colour}`}>
      {pct}% accurate
    </span>
  )
}

function PronunciationDrill() {
  const [phrase, setPhrase] = useState(PRESET_PHRASES[0])
  const [custom, setCustom] = useState('')
  const [useCustom, setUseCustom] = useState(false)

  const [state, setState] = useState<DrillState>('idle')
  const [result, setResult] = useState<PronunciationCheckResponse | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])

  const activePhrase = useCustom ? custom.trim() : phrase

  async function startRecording() {
    setResult(null)
    setErrorMsg(null)
    chunksRef.current = []

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setErrorMsg(
        'Microphone access was denied. Please allow microphone access in your browser settings and try again.',
      )
      setState('error')
      return
    }

    const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4'
    const recorder = new MediaRecorder(stream, { mimeType })
    mediaRecorderRef.current = recorder

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data)
    }

    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      const blob = new Blob(chunksRef.current, { type: mimeType })
      setState('processing')
      try {
        const res = await checkPronunciation(blob, activePhrase)
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

  return (
    <div>
      <h1 className="text-2xl font-semibold text-white">Pronunciation Drill</h1>
      <p className="mt-1 text-sm text-gray-400">
        Select a phrase, record yourself saying it, and get word-by-word feedback.
      </p>

      {/* Phrase selector */}
      <div className="mt-6 rounded-xl border border-[#2a2a3a] bg-[#111118] p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-300">Phrase</label>
          <select
            value={useCustom ? '__custom__' : phrase}
            onChange={(e) => {
              if (e.target.value === '__custom__') {
                setUseCustom(true)
              } else {
                setUseCustom(false)
                setPhrase(e.target.value)
              }
              reset()
            }}
            className="mt-1 block w-full rounded-lg border border-[#2a2a3a] bg-[#1a1a24] px-3 py-2 text-sm text-white focus:border-violet-500 focus:outline-none"
          >
            {PRESET_PHRASES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
            <option value="__custom__">Custom phrase…</option>
          </select>
        </div>

        {useCustom && (
          <div>
            <label className="block text-sm font-medium text-gray-300">Custom phrase</label>
            <input
              type="text"
              value={custom}
              onChange={(e) => { setCustom(e.target.value); reset() }}
              placeholder="Type a Spanish phrase…"
              className="mt-1 block w-full rounded-lg border border-[#2a2a3a] bg-[#1a1a24] px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none"
            />
          </div>
        )}

        {/* Active phrase display */}
        {activePhrase && (
          <div className="rounded-lg border border-[#2a2a3a] bg-[#0a0a0f] px-4 py-3">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-1">Say this</p>
            <p className="text-lg text-white">{activePhrase}</p>
          </div>
        )}

        {/* Record / Stop button */}
        <div className="flex items-center gap-4">
          {state !== 'recording' ? (
            <button
              type="button"
              disabled={state === 'processing' || !activePhrase}
              onClick={startRecording}
              className="flex items-center gap-2 rounded-lg bg-violet-600 px-5 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
            >
              <span className="inline-block h-2 w-2 rounded-full bg-white" />
              {state === 'processing' ? 'Processing…' : 'Record'}
            </button>
          ) : (
            <button
              type="button"
              onClick={stopRecording}
              className="flex items-center gap-2 rounded-lg bg-red-600 px-5 py-2 text-sm font-medium text-white hover:bg-red-500"
            >
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-white" />
              Stop
            </button>
          )}

          {state === 'result' && (
            <button
              type="button"
              onClick={reset}
              className="rounded-lg border border-[#2a2a3a] px-4 py-2 text-sm font-medium text-gray-300 hover:bg-[#1a1a24] hover:text-white"
            >
              Try again
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {state === 'error' && errorMsg && (
        <div className="mt-4 rounded-lg border border-red-800 bg-red-900/40 px-4 py-3 text-sm text-red-400">
          {errorMsg}
        </div>
      )}

      {/* Result */}
      {state === 'result' && result && (
        <div className="mt-4 space-y-4">
          <div className="flex items-center gap-4">
            <AccuracyBadge accuracy={result.accuracy} />
          </div>

          <div className="rounded-xl border border-[#2a2a3a] bg-[#111118] p-5 space-y-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-2">
                Word-by-word feedback
              </p>
              <p className="flex flex-wrap gap-1.5 text-base leading-relaxed">
                {result.diff.map((item, i) => (
                  <WordToken key={i} item={item} />
                ))}
              </p>
            </div>

            <div className="border-t border-[#2a2a3a] pt-3">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-1">
                Listener model
              </p>
              <p className="text-sm text-gray-300">
                {result.transcribed_text || <span className="italic text-gray-500">(nothing)</span>}
              </p>
            </div>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-4 text-xs text-gray-500">
            <span><span className="text-green-400">■</span> Correct</span>
            <span><span className="text-red-400">■</span> Missing word</span>
            <span><span className="text-yellow-400">■</span> Substituted</span>
            <span><span className="text-gray-500 line-through">■</span> Extra word</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default PronunciationDrill
