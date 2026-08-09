import { AlertTriangle, Lightbulb, Wrench } from 'lucide-react'
import LessonRenderer from '../LessonRenderer'
import CodeBlock from '../CodeBlock'
import Callout from '../Callout'
import { Card, IconBadge } from '../ui'

interface KeyConcept {
  name: string
  definition: string
  example?: string
}

interface StructuredLesson {
  key_concepts?: KeyConcept[]
  worked_example?: string
  common_pitfalls?: string[]
  practice_prompts?: string[]
  description?: string
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

/**
 * Lesson bodies come back as structured JSON from the generation prompt, but
 * older courses (and any parse failure) fall back to markdown.
 */
export default function LessonBody({ description }: { description: string }) {
  if (description.trimStart().startsWith('{')) {
    try {
      const data: StructuredLesson = JSON.parse(description)
      const concepts = data.key_concepts ?? []
      const workedExample = data.worked_example ?? null
      const pitfalls = data.common_pitfalls ?? []
      const plainDesc = data.description ?? null

      return (
        <div className="space-y-10">
          {plainDesc && <p className="text-body-lg text-fg-muted text-pretty">{plainDesc}</p>}

          {concepts.length > 0 && (
            <Section icon={Lightbulb} title="Key concepts" tone="brand">
              <div className="grid gap-3 sm:grid-cols-2">
                {concepts.map((c) => (
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

          {workedExample && (
            <Section icon={Wrench} title="Worked example" tone="info">
              <CodeBlock code={workedExample} language="python" />
            </Section>
          )}

          {pitfalls.length > 0 && (
            <Section icon={AlertTriangle} title="Common pitfalls" tone="warn">
              <div className="space-y-2">
                {pitfalls.map((p, i) => (
                  <Callout key={i} variant="warning">
                    {p}
                  </Callout>
                ))}
              </div>
            </Section>
          )}
        </div>
      )
    } catch {
      // Malformed JSON — fall through to the markdown renderer.
    }
  }

  return <LessonRenderer content={description} />
}
