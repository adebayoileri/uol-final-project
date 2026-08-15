import { useEffect, useRef, useState } from 'react'
import { motion, LayoutGroup } from 'motion/react'
import { Headphones, Pause, Play } from 'lucide-react'
import { API_URL } from '../config'
import { Card, Spinner } from './ui'
import { springDefault } from '../motion/springs'
import { cn } from '../lib/cn'

type PlayerState = 'idle' | 'loading' | 'playing' | 'paused' | 'done' | 'error'

const SPEEDS = [0.75, 1, 1.25, 1.5] as const

interface AudioPlayerProps {
  lessonId: string
}

function fmt(secs: number) {
  if (!Number.isFinite(secs)) return '0:00'
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function AudioPlayer({ lessonId }: AudioPlayerProps) {
  const [state, setState] = useState<PlayerState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [duration, setDuration] = useState(0)
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1)

  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    return () => {
      audioRef.current?.pause()
    }
  }, [])

  async function handlePlay() {
    if (state === 'paused' && audioRef.current) {
      audioRef.current.play()
      setState('playing')
      return
    }

    setState('loading')
    setError(null)

    try {
      const res = await fetch(`${API_URL}/lessons/${lessonId}/narration`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.detail ?? `Server error ${res.status}`)
      }
      const { url } = (await res.json()) as { url: string }

      const audio = new Audio(`${API_URL}${url}`)
      audio.playbackRate = speed
      audioRef.current = audio

      audio.addEventListener('loadedmetadata', () => setDuration(audio.duration))
      audio.addEventListener('timeupdate', () => setProgress(audio.currentTime))
      audio.addEventListener('ended', () => setState('done'))
      audio.addEventListener('error', () => {
        setError('Audio playback failed.')
        setState('error')
      })

      await audio.play()
      setState('playing')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Narration generation failed.')
      setState('error')
    }
  }

  function handlePause() {
    audioRef.current?.pause()
    setState('paused')
  }

  function handleSeek(e: React.ChangeEvent<HTMLInputElement>) {
    const t = Number(e.target.value)
    if (audioRef.current) {
      audioRef.current.currentTime = t
      setProgress(t)
    }
  }

  function handleSpeed(s: (typeof SPEEDS)[number]) {
    setSpeed(s)
    if (audioRef.current) audioRef.current.playbackRate = s
  }

  const isPlaying = state === 'playing'
  const isLoading = state === 'loading'
  const hasAudio = state !== 'idle' && state !== 'loading' && state !== 'error'

  const statusLabel = isLoading
    ? 'Generating narration…'
    : state === 'error'
      ? 'Narration unavailable'
      : state === 'done'
        ? 'Finished'
        : state === 'idle'
          ? 'Listen to this lesson'
          : 'Narration'

  return (
    <Card padding="md">
      <div className="flex items-center gap-4">
        <motion.button
          whileTap={{ scale: 0.94 }}
          transition={springDefault}
          onClick={isPlaying ? handlePause : handlePlay}
          disabled={isLoading}
          className="bg-brand-500 hover:bg-brand-400 grid size-11 shrink-0 place-items-center rounded-full text-white transition-colors disabled:opacity-50"
          aria-label={isPlaying ? 'Pause narration' : 'Play narration'}
        >
          {isLoading ? (
            <Spinner size="md" />
          ) : isPlaying ? (
            <Pause size={17} fill="currentColor" />
          ) : (
            <Play size={17} fill="currentColor" className="ml-0.5" />
          )}
        </motion.button>

        <div className="min-w-0 flex-1">
          <p className="text-callout text-fg-muted flex items-center gap-1.5">
            <Headphones size={13} className="text-fg-faint shrink-0" aria-hidden="true" />
            {statusLabel}
          </p>

          {hasAudio && duration > 0 && (
            <div className="mt-2 flex items-center gap-3">
              <input
                type="range"
                min={0}
                max={duration}
                step={0.5}
                value={progress}
                onChange={handleSeek}
                aria-label="Seek"
                className={cn(
                  'h-1 flex-1 cursor-pointer appearance-none rounded-full',
                  'bg-surface-raised',
                  '[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:size-3',
                  '[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-brand-400',
                  '[&::-moz-range-thumb]:size-3 [&::-moz-range-thumb]:border-0',
                  '[&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-brand-400',
                )}
                style={{
                  background: `linear-gradient(to right, var(--color-brand-500) ${
                    (progress / duration) * 100
                  }%, var(--color-surface-raised) ${(progress / duration) * 100}%)`,
                }}
              />
              <span className="text-caption text-fg-faint shrink-0 tabular-nums">
                {fmt(progress)} / {fmt(duration)}
              </span>
            </div>
          )}
        </div>

        <LayoutGroup id={`speed-${lessonId}`}>
          <div className="bg-surface-raised flex shrink-0 gap-0.5 rounded-md p-0.5">
            {SPEEDS.map((s) => (
              <button
                key={s}
                onClick={() => handleSpeed(s)}
                aria-pressed={speed === s}
                className="text-caption relative rounded-sm px-2 py-1 tabular-nums"
              >
                {speed === s && (
                  <motion.span
                    layoutId="speed-pill"
                    transition={springDefault}
                    className="bg-brand-500 absolute inset-0 rounded-sm"
                  />
                )}
                <span className={cn('relative', speed === s ? 'text-white' : 'text-fg-subtle')}>
                  {s}×
                </span>
              </button>
            ))}
          </div>
        </LayoutGroup>
      </div>

      {error && (
        <p role="alert" className="text-caption text-danger mt-2">
          {error}
        </p>
      )}
    </Card>
  )
}
