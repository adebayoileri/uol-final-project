import type { Transition, Variants } from 'motion/react'

/**
 * Apple parameterises springs as damping ratio + response rather than
 * mass/stiffness/damping. Motion's `bounce` + `duration` maps onto that
 * closely, where bounce ≈ 1 − damping.
 *
 * House rule: bounce > 0 ONLY where a gesture carried momentum or where the
 * moment is a deliberate celebration. Overshoot on something that merely faded
 * in reads as noise.
 */

/** damping 1.0 / response 0.4 — the default for everything. No overshoot. */
export const springDefault: Transition = { type: 'spring', bounce: 0, duration: 0.4 }

/** damping 1.0 / response 0.28 — press feedback, toggles, chips. */
export const springSnappy: Transition = { type: 'spring', bounce: 0, duration: 0.28 }

/** damping ~0.8 / response 0.4 — after a flick, a throw, or a decisive commit. */
export const springMomentum: Transition = { type: 'spring', bounce: 0.2, duration: 0.4 }

/** damping ~0.8 / response 0.3 — sheets, drawers, accordions. */
export const springSheet: Transition = { type: 'spring', bounce: 0.2, duration: 0.3 }

/** Non-physical cross-fades. Exits stay short: latency is where directness dies. */
export const fadeFast: Transition = { duration: 0.15, ease: [0.4, 0, 1, 1] }
export const fadeIn: Transition = { duration: 0.22, ease: [0, 0, 0.2, 1] }

/** Stagger a list in. Pair `listContainer` on the wrapper with `listItem` on each child. */
export const listContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04, delayChildren: 0.03 } },
}

export const listItem: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: springDefault },
}

/** A single element arriving under its own steam. */
export const riseIn: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: springDefault },
}
