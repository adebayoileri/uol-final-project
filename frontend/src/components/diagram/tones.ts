import type { DiagramTone } from '../../api'

/**
 * Diagram tones as CSS custom-property references.
 *
 * Every value is a `var()` rather than a literal, and that is load-bearing: the
 * app resolves light and dark from the same markup, so a hex here would be
 * correct in one theme and wrong in the other. Logo.tsx already proves var()
 * resolves inside inline SVG.
 *
 * `fill` is the saturated block colour and `on` is what stays legible on top of
 * it. They are always used as a pair — brand-500 holds its value across themes,
 * which brand-200/300/400 deliberately do not.
 */
export const TONE_FILL: Record<DiagramTone, string> = {
  brand: 'var(--color-brand-500)',
  success: 'var(--color-success)',
  warn: 'var(--color-warn)',
  danger: 'var(--color-danger)',
  info: 'var(--color-info)',
  neutral: 'var(--color-surface-raised)',
}

export const TONE_ON: Record<DiagramTone, string> = {
  brand: 'var(--color-on-brand)',
  success: 'var(--color-canvas)',
  warn: 'var(--color-canvas)',
  danger: 'var(--color-canvas)',
  info: 'var(--color-canvas)',
  neutral: 'var(--color-fg)',
}

/** Line and text colour for a tone used as an outline rather than a fill. */
export const TONE_STROKE: Record<DiagramTone, string> = {
  brand: 'var(--color-brand-500)',
  success: 'var(--color-success)',
  warn: 'var(--color-warn)',
  danger: 'var(--color-danger)',
  info: 'var(--color-info)',
  neutral: 'var(--color-border-strong)',
}

export function toneFill(tone: DiagramTone | string): string {
  return TONE_FILL[tone as DiagramTone] ?? TONE_FILL.neutral
}

export function toneOn(tone: DiagramTone | string): string {
  return TONE_ON[tone as DiagramTone] ?? TONE_ON.neutral
}

export function toneStroke(tone: DiagramTone | string): string {
  return TONE_STROKE[tone as DiagramTone] ?? TONE_STROKE.neutral
}
