import { AlertTriangle, HelpCircle, Lightbulb, Shapes, Wrench } from 'lucide-react'
import type { DiagramSpec, LessonContent } from '../../api'
import LessonRenderer from '../LessonRenderer'
import CodeBlock from '../CodeBlock'
import Callout from '../Callout'
import Diagram from '../diagram/Diagram'
import { Button, Card, IconBadge, Skeleton } from '../ui'

export type EnrichState = 'idle' | 'loading' | 'ready' | 'unavailable'

interface LessonBodyProps {
  description: string
  content: LessonContent | null
  state: EnrichState
  onRetry: () => void
  /** Null until generation has been attempted; empty means none was needed. */
  diagrams: DiagramSpec[] | null
  diagramsLoading: boolean
}

function Section({
  icon,
  title,
  tone,
  children,
}: {
  icon: typeof Lightbulb
  title: string
  tone: 'brand' | 'info' | 'warn'
  children: React.ReactNode
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-headline text-fg flex items-center gap-2.5">
        <IconBadge icon={icon} tone={tone} size="sm" />
        {title}
      </h2>
      {children}
    </section>
  )
}

/** Occupies the same boxes the real content will, so nothing shifts on arrival. */
function EnrichingSkeleton() {
  return (
    <div className="space-y-10" aria-busy="true" aria-label="Writing the full lesson">
      <section className="space-y-3">
        <Skeleton variant="title" width="11rem" />
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton variant="block" height="7rem" />
          <Skeleton variant="block" height="7rem" />
        </div>
      </section>
      <section className="space-y-3">
        <Skeleton variant="title" width="13rem" />
        <Skeleton variant="block" height="9rem" />
      </section>
      <p className="text-caption text-fg-subtle">
        Writing the full lesson — this takes a few seconds.
      </p>
    </div>
  )
}

/**
 * The prose summary renders immediately and is never gated behind enrichment;
 * the deep content is a progressive enhancement layered underneath it.
 */
export default function LessonBody({
  description,
  content,
  state,
  onRetry,
  diagrams,
  diagramsLoading,
}: LessonBodyProps) {
  return (
    <div className="space-y-10">
      {description.trim() && <LessonRenderer content={description} />}

      {state === 'loading' && <EnrichingSkeleton />}

      {content && (
        <>
          {content.key_concepts.length > 0 && (
            <Section icon={Lightbulb} title="Key concepts" tone="brand">
              <div className="grid gap-3 sm:grid-cols-2">
                {content.key_concepts.map((c) => (
                  <Card key={c.name} padding="md">
                    <h3 className="text-headline text-brand-200">{c.name}</h3>
                    <p className="text-callout text-fg-muted mt-1.5">{c.definition}</p>
                    {c.example && (
                      <p className="text-caption text-fg-subtle bg-canvas-elevated border-hairline mt-3 rounded-md border px-2.5 py-2 font-mono">
                        {c.example}
                      </p>
                    )}
                  </Card>
                ))}
              </div>
            </Section>
          )}

          {/* Between the concepts and the worked example on purpose: a diagram
              explains the idea, the worked example then applies it. Absent and
              failed both render as silence — a diagram is an enhancement, and
              an apology for a missing one costs more attention than it saves. */}
          {diagramsLoading && (
            <section className="space-y-3" aria-busy="true" aria-label="Drawing a diagram">
              <Skeleton variant="title" width="7rem" />
              <Skeleton variant="block" height="14rem" />
            </section>
          )}

          {diagrams && diagrams.length > 0 && (
            <Section icon={Shapes} title={diagrams.length > 1 ? 'Diagrams' : 'Diagram'} tone="brand">
              <div className="space-y-4">
                {diagrams.map((spec) => (
                  <Diagram key={spec.id} spec={spec} />
                ))}
              </div>
            </Section>
          )}

          {content.worked_example && (
            <Section icon={Wrench} title="Worked example" tone="info">
              <CodeBlock code={content.worked_example} language="text" filename="Walkthrough" />
            </Section>
          )}

          {content.common_pitfalls.length > 0 && (
            <Section icon={AlertTriangle} title="Common pitfalls" tone="warn">
              <div className="space-y-2">
                {content.common_pitfalls.map((p, i) => (
                  <Callout key={i} variant="warning">
                    {p}
                  </Callout>
                ))}
              </div>
            </Section>
          )}

          {content.practice_prompts.length > 0 && (
            <Section icon={HelpCircle} title="Think about it" tone="info">
              <div className="space-y-2">
                {content.practice_prompts.map((p, i) => (
                  <Callout key={i} variant="tip">
                    {p}
                  </Callout>
                ))}
              </div>
            </Section>
          )}
        </>
      )}

      {state === 'unavailable' && (
        <Callout variant="note">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            The deeper content for this lesson couldn't be generated just now.
            <Button variant="link" size="sm" onClick={onRetry}>
              Try again
            </Button>
          </span>
        </Callout>
      )}
    </div>
  )
}
