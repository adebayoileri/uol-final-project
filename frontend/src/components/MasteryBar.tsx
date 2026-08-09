import { ProgressBar } from './ui'

interface MasteryBarProps {
  name: string
  /** 0.0–1.0 */
  mastery: number
}

/** Tone encodes the level, so a weak concept is visible at a glance. */
export default function MasteryBar({ name, mastery }: MasteryBarProps) {
  const tone = mastery < 0.4 ? 'danger' : mastery < 0.7 ? 'warn' : 'success'
  return <ProgressBar value={mastery} size="sm" tone={tone} label={name} showValue />
}
