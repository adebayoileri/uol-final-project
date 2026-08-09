import { useEffect, useRef, useState } from 'react'

type PlayerState = 'idle' | 'loading' | 'playing' | 'paused' | 'done' | 'error'

const SPEEDS = [0.75, 1, 1.25, 1.5] as const

interface AudioPlayerProps {
  lessonId: string
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
      const res = await fetch(`/api/lessons/${lessonId}/narration`, { method: 'POST' })
      if (!res.ok) {
        const msg = await res.text()
        throw new Error(msg || `Server error ${res.status}`)
      }
      const { url } = (await res.json()) as { url: string }

      const audio = new Audio(`/api${url}`)
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

  function handleSpeed(s: typeof speed) {
    setSpeed(s)
    if (audioRef.current) audioRef.current.playbackRate = s
  }

  function fmt(secs: number) {
    const m = Math.floor(secs / 60)
    const s = Math.floor(secs % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const isPlaying = state === 'playing'
  const isLoading = state === 'loading'
  const hasAudio = state !== 'idle' && state !== 'loading' && state !== 'error'

  return (
    <div className="rounded-lg border border-[#2a2a3a] bg-[#111118] p-3 flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <button
          onClick={isPlaying ? handlePause : handlePlay}
          disabled={isLoading}
          className="flex items-center justify-center w-8 h-8 rounded-full bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-xs shrink-0"
          aria-label={isPlaying ? 'Pause' : 'Play narration'}
        >
          {isLoading ? (
            <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          ) : isPlaying ? (
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
              <rect x="5" y="4" width="3" height="12" rx="1" />
              <rect x="12" y="4" width="3" height="12" rx="1" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5 ml-0.5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M5 4l11 6-11 6V4z" />
            </svg>
          )}
        </button>

        <div className="flex-1 min-w-0">
          <span className="text-xs text-gray-400">
            {state === 'idle' ? 'Play narration' :
             isLoading ? 'Generating audio…' :
             state === 'error' ? 'Error' :
             state === 'done' ? 'Finished' : 'Narration'}
          </span>

          {hasAudio && duration > 0 && (
            <div className="flex items-center gap-2 mt-1">
              <input
                type="range"
                min={0}
                max={duration}
                step={0.5}
                value={progress}
                onChange={handleSeek}
                className="flex-1 h-1 accent-violet-500 cursor-pointer"
              />
              <span className="text-xs text-gray-500 tabular-nums shrink-0">
                {fmt(progress)} / {fmt(duration)}
              </span>
            </div>
          )}
        </div>

        <div className="flex gap-1 shrink-0">
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => handleSpeed(s)}
              className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                speed === s
                  ? 'bg-violet-600 text-white'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}
    </div>
  )
}
