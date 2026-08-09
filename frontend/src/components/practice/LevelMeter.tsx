import { useEffect, useRef } from 'react'

const BARS = 5

/**
 * Real input level from the live MediaStream, not a decorative loop — the bars
 * respond to the user's voice, which is the point of showing them at all.
 * Written straight to style.transform so it never re-renders React per frame.
 */
export default function LevelMeter({ stream }: { stream: MediaStream | null }) {
  const barRefs = useRef<Array<HTMLSpanElement | null>>([])

  useEffect(() => {
    if (!stream) return

    const AudioCtx =
      window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    if (!AudioCtx) return

    const ctx = new AudioCtx()
    const source = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 128
    analyser.smoothingTimeConstant = 0.7
    source.connect(analyser)

    const data = new Uint8Array(analyser.frequencyBinCount)
    let raf = 0

    const tick = () => {
      analyser.getByteFrequencyData(data)
      const perBar = Math.floor(data.length / BARS)
      for (let i = 0; i < BARS; i++) {
        let sum = 0
        for (let j = i * perBar; j < (i + 1) * perBar; j++) sum += data[j]
        const avg = sum / perBar / 255
        const scale = 0.15 + Math.min(1, avg * 2.4) * 0.85
        const el = barRefs.current[i]
        if (el) el.style.transform = `scaleY(${scale})`
      }
      raf = requestAnimationFrame(tick)
    }
    tick()

    return () => {
      cancelAnimationFrame(raf)
      source.disconnect()
      ctx.close().catch(() => {})
    }
  }, [stream])

  return (
    <div className="flex h-8 items-center justify-center gap-1" aria-hidden="true">
      {Array.from({ length: BARS }).map((_, i) => (
        <span
          key={i}
          ref={(el) => {
            barRefs.current[i] = el
          }}
          className="bg-danger h-full w-1 origin-center rounded-full transition-transform duration-75"
          style={{ transform: 'scaleY(0.15)' }}
        />
      ))}
    </div>
  )
}
