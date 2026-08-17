import { useCallback, useEffect, useMemo, useState } from 'react'
import { useReducedMotion } from 'motion/react'
import type { DiagramStep } from '../../api'

const STEP_MS = 2200

export interface StepState {
  /** True when this diagram has a staged reveal worth showing controls for. */
  stepped: boolean
  index: number
  count: number
  label: string | null
  playing: boolean
  /** Elements revealed so far. Empty set means "no gating — show everything". */
  visible: Set<string>
  /** Elements emphasised at the current step only. */
  active: Set<string>
  play: () => void
  pause: () => void
  next: () => void
  prev: () => void
  goTo: (index: number) => void
}

/**
 * Drives a diagram's staged reveal.
 *
 * `show` accumulates and `highlight` does not: revealing is a statement about
 * what exists by now, emphasising is a statement about the current moment.
 *
 * Under reduced motion this reports the final step with nothing gated and never
 * auto-plays — the same bargain Confetti makes, where the gentler equivalent of
 * a moving thing is the finished thing rather than a broken one. The step
 * captions stay reachable by the controls, so no content is lost.
 */
export function useDiagramSteps(steps: DiagramStep[]): StepState {
  const reduced = useReducedMotion()
  const stepped = steps.length > 1
  const count = steps.length

  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    if (!playing || !stepped) return
    const timer = window.setTimeout(() => {
      setIndex((i) => {
        if (i + 1 >= count) {
          setPlaying(false)
          return i
        }
        return i + 1
      })
    }, STEP_MS)
    return () => window.clearTimeout(timer)
  }, [playing, index, count, stepped])

  const play = useCallback(() => {
    // Replaying from the end should restart rather than sit there doing nothing.
    setIndex((i) => (i + 1 >= count ? 0 : i))
    setPlaying(true)
  }, [count])

  const pause = useCallback(() => setPlaying(false), [])
  const next = useCallback(() => {
    setPlaying(false)
    setIndex((i) => Math.min(i + 1, count - 1))
  }, [count])
  const prev = useCallback(() => {
    setPlaying(false)
    setIndex((i) => Math.max(i - 1, 0))
  }, [])
  const goTo = useCallback(
    (target: number) => {
      setPlaying(false)
      setIndex(Math.min(Math.max(target, 0), Math.max(count - 1, 0)))
    },
    [count],
  )

  const effectiveIndex = reduced && stepped ? count - 1 : index

  const { visible, active } = useMemo(() => {
    if (!stepped) return { visible: new Set<string>(), active: new Set<string>() }

    const shown = new Set<string>()
    for (let i = 0; i <= effectiveIndex; i++) {
      for (const id of steps[i].show) shown.add(id)
    }
    // A diagram whose steps only ever highlight is not gating visibility at
    // all; an empty set is the renderers' signal to draw everything.
    return {
      visible: reduced ? new Set<string>() : shown,
      active: new Set(steps[effectiveIndex]?.highlight ?? []),
    }
  }, [steps, effectiveIndex, stepped, reduced])

  return {
    stepped,
    index: effectiveIndex,
    count,
    label: stepped ? (steps[effectiveIndex]?.label ?? null) : null,
    playing: playing && !reduced,
    visible,
    active,
    play,
    pause,
    next,
    prev,
    goTo,
  }
}
