import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react'
import { VIEW } from './layout'
import type { StepState } from './useDiagramSteps'
import { cn } from '../../lib/cn'

interface DiagramFrameProps {
  title: string
  caption: string
  steps: StepState
  children: React.ReactNode
}

/**
 * Shared chrome for every diagram kind: the accessible description, the square
 * drawing surface, the caption and the step control.
 *
 * The SVG carries role="img" plus a <title>/<desc> pair rather than being
 * aria-hidden with a visible caption alone, because the caption states the
 * conclusion while the title names the thing — a screen-reader user needs both,
 * and the shapes inside carry no text a reader could otherwise reach.
 */
export default function DiagramFrame({ title, caption, steps, children }: DiagramFrameProps) {
  const description = steps.label ? `${caption} ${steps.label}` : caption

  return (
    <figure className="border-hairline bg-canvas-elevated overflow-hidden rounded-lg border">
      <div className="p-3 sm:p-4">
        <svg
          viewBox={`0 0 ${VIEW} ${VIEW}`}
          role="img"
          className="mx-auto block h-auto w-full max-w-md"
        >
          <title>{title}</title>
          <desc>{description}</desc>
          {children}
        </svg>
      </div>

      {steps.stepped && (
        <div className="border-hairline bg-surface flex items-center gap-2 border-t px-3 py-2">
          <button
            type="button"
            onClick={steps.playing ? steps.pause : steps.play}
            aria-label={steps.playing ? 'Pause the walkthrough' : 'Play the walkthrough'}
            className="text-fg-muted hover:text-fg hover:bg-surface-raised grid size-8 shrink-0 place-items-center rounded-md transition-colors"
          >
            {steps.playing ? <Pause size={15} aria-hidden="true" /> : <Play size={15} aria-hidden="true" />}
          </button>
          <button
            type="button"
            onClick={steps.prev}
            disabled={steps.index === 0}
            aria-label="Previous step"
            className="text-fg-muted hover:text-fg hover:bg-surface-raised grid size-8 shrink-0 place-items-center rounded-md transition-colors disabled:opacity-40"
          >
            <ChevronLeft size={15} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={steps.next}
            disabled={steps.index >= steps.count - 1}
            aria-label="Next step"
            className="text-fg-muted hover:text-fg hover:bg-surface-raised grid size-8 shrink-0 place-items-center rounded-md transition-colors disabled:opacity-40"
          >
            <ChevronRight size={15} aria-hidden="true" />
          </button>

          {/* The step text is the content, so it is announced on change; the
              dots below are decoration and stay out of the accessibility tree. */}
          <p className="text-caption text-fg-muted min-w-0 flex-1 truncate" aria-live="polite">
            <span className="text-fg-faint tabular-nums">
              {steps.index + 1}/{steps.count}
            </span>{' '}
            {steps.label}
          </p>

          <div className="hidden shrink-0 items-center gap-1 sm:flex" aria-hidden="true">
            {Array.from({ length: steps.count }).map((_, i) => (
              <span
                key={i}
                className={cn(
                  'size-1.5 rounded-full transition-colors',
                  i <= steps.index ? 'bg-brand-500' : 'bg-border',
                )}
              />
            ))}
          </div>
        </div>
      )}

      <figcaption className="border-hairline text-caption text-fg-subtle border-t px-3 py-2.5">
        {caption}
      </figcaption>
    </figure>
  )
}
