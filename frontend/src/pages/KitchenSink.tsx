import { useState } from 'react'
import {
  BookOpen,
  Brain,
  CalendarClock,
  Clock,
  Flame,
  Mic,
  Target,
  Trophy,
} from 'lucide-react'
import {
  Badge,
  Button,
  ButtonLink,
  Card,
  CardListSkeleton,
  EmptyState,
  ErrorState,
  Eyebrow,
  Field,
  IconBadge,
  Input,
  PageHeader,
  ProgressBar,
  SectionHeading,
  Segmented,
  Select,
  Skeleton,
  Spinner,
  StatTile,
  Textarea,
  VerdictPanel,
  useToast,
} from '../components/ui'
import type { Tone } from '../components/ui'
import Diagram from '../components/diagram/Diagram'
import { SAMPLE_DIAGRAMS } from '../components/diagram/samples'

const TONES: Tone[] = ['brand', 'success', 'warn', 'danger', 'info', 'neutral']

/**
 * Dev-only reference page. Renders every primitive in every variant so the
 * tokens can be tuned against real components rather than in the abstract.
 */
export default function KitchenSink() {
  const toast = useToast()
  const [seg, setSeg] = useState<'short_term' | 'long_term'>('short_term')

  return (
    <div className="space-y-12 pb-24">
      <PageHeader
        eyebrow="Dev only"
        title="Kitchen sink"
        description="Every UI primitive in every variant. Not routed in production builds."
        actions={
          <Button onClick={() => toast({ title: 'Toast fired', tone: 'success' })}>
            Fire a toast
          </Button>
        }
      />

      <section className="space-y-4">
        <SectionHeading title="Type scale" />
        <Card padding="lg" className="space-y-3">
          <p className="text-display-2xl">Display 2xl</p>
          <p className="text-display-xl">Display xl</p>
          <p className="text-display-lg">Display lg</p>
          <p className="text-title-lg">Title lg</p>
          <p className="text-title">Title</p>
          <p className="text-headline">Headline</p>
          <p className="text-body-lg text-fg-muted">Body lg — the long-form reading size.</p>
          <p className="text-body text-fg-muted">Body — the default paragraph size.</p>
          <p className="text-callout text-fg-muted">Callout — dense UI text.</p>
          <p className="text-caption text-fg-subtle">Caption — metadata.</p>
          <Eyebrow>Eyebrow — positive tracking</Eyebrow>
        </Card>
      </section>

      <section className="space-y-4">
        <SectionHeading title="Surfaces" description="Each step must be distinguishable." />
        <div className="grid gap-3 sm:grid-cols-4">
          {[
            ['canvas', 'bg-canvas'],
            ['canvas-elevated', 'bg-canvas-elevated'],
            ['surface', 'bg-surface'],
            ['surface-raised', 'bg-surface-raised'],
          ].map(([name, cls]) => (
            <div key={name} className={`rounded-lg border border-border p-6 ${cls}`}>
              <p className="text-caption text-fg-subtle">{name}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <SectionHeading title="Buttons" />
        <Card padding="lg" className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary">Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="danger">Danger</Button>
            <Button variant="link">Link</Button>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm">Small</Button>
            <Button size="md">Medium</Button>
            <Button size="lg">Large</Button>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button icon={Flame}>With icon</Button>
            <Button icon={Target} iconPosition="right" variant="secondary">
              Icon right
            </Button>
            <Button loading>Loading</Button>
            <Button disabled>Disabled</Button>
            <ButtonLink to="/">Button link</ButtonLink>
          </div>
        </Card>
      </section>

      <section className="space-y-4">
        <SectionHeading title="Badges and icon badges" />
        <Card padding="lg" className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {TONES.map((t) => (
              <Badge key={t} tone={t}>
                {t}
              </Badge>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="warn" icon={Flame}>
              12 due
            </Badge>
            <Badge tone="success" dot>
              Completed
            </Badge>
            <Badge size="sm">Small</Badge>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {(['sm', 'md', 'lg', 'xl'] as const).map((s) => (
              <IconBadge key={s} icon={Brain} size={s} />
            ))}
            {TONES.map((t) => (
              <IconBadge key={t} icon={Trophy} tone={t} />
            ))}
          </div>
        </Card>
      </section>

      <section className="space-y-4">
        <SectionHeading title="Stat tiles" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile icon={BookOpen} label="Lessons done" value={12} countUp />
          <StatTile icon={Brain} label="Mastery" value={78} unit="%" tone="success" countUp />
          <StatTile icon={Flame} label="Day streak" value={5} tone="warn" countUp />
          <StatTile icon={Clock} label="Time left" value="2h 15m" tone="info" hint="at ~20m/day" />
        </div>
      </section>

      <section className="space-y-4">
        <SectionHeading title="Progress" />
        <Card padding="lg" className="space-y-5">
          <ProgressBar value={0.33} size="xs" />
          <ProgressBar value={0.62} size="sm" label="Course progress" showValue />
          <ProgressBar value={0.88} size="md" tone="success" label="Mastery" showValue />
          <ProgressBar value={0.25} size="sm" tone="danger" label="Weak concept" showValue />
        </Card>
      </section>

      <section className="space-y-4">
        <SectionHeading title="Form controls" />
        <Card padding="lg" className="max-w-lg space-y-4">
          <Field label="Goal" hint="What do you want to learn?">
            {(p) => <Textarea rows={3} placeholder="Teach me linear regression…" {...p} />}
          </Field>
          <Field label="Category">
            {(p) => (
              <Select {...p}>
                <option>Programming</option>
                <option>Language</option>
              </Select>
            )}
          </Field>
          <Field label="Answer" error="That doesn't look right.">
            {(p) => <Input placeholder="Type an answer…" {...p} />}
          </Field>
          <Segmented
            label="Duration"
            value={seg}
            onChange={setSeg}
            options={[
              { value: 'short_term', label: 'Short term' },
              { value: 'long_term', label: 'Long term' },
            ]}
          />
        </Card>
      </section>

      <section className="space-y-4">
        <SectionHeading title="Verdicts" />
        <div className="grid gap-3 lg:grid-cols-3">
          <VerdictPanel verdict="correct" score={0.94} signalUsed="embedding" />
          <VerdictPanel
            verdict="incorrect"
            score={0.61}
            explanation="You named the right method but missed the intercept term."
            signalUsed="embedding+llm"
          />
          <VerdictPanel
            verdict="incorrect"
            score={0.12}
            explanation="This describes classification, not regression."
            signalUsed="llm"
          />
        </div>
      </section>

      <section className="space-y-4">
        <SectionHeading title="Loading, empty, error" />
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <Spinner size="sm" />
            <Spinner size="md" />
            <Spinner size="lg" />
          </div>
          <Card padding="lg" className="space-y-4">
            <Skeleton variant="title" width="40%" />
            <Skeleton lines={3} />
            <Skeleton variant="block" height="5rem" />
          </Card>
          <CardListSkeleton count={3} />
          <Card padding="none">
            <EmptyState
              icon={CalendarClock}
              title="Nothing due right now"
              description="Your next review lands tomorrow morning."
              action={<Button icon={BookOpen}>Study a lesson</Button>}
            />
          </Card>
          <Card padding="none">
            <ErrorState
              message="The course could not be loaded."
              onRetry={() => toast({ title: 'Retried', tone: 'info' })}
              backTo="/"
            />
          </Card>
          <ErrorState inline message="Certificate generation failed." onRetry={() => {}} />
        </div>
      </section>

      <section className="space-y-4">
        <SectionHeading title="Cards" />
        <div className="grid gap-3 sm:grid-cols-3">
          {([0, 1, 2, 3] as const).map((e) => (
            <Card key={e} elevation={e} padding="lg">
              <p className="text-callout text-fg-muted">elevation {e}</p>
            </Card>
          ))}
          <Card interactive padding="lg">
            <p className="text-callout text-fg-muted">interactive (hover)</p>
          </Card>
        </div>
      </section>

      <section className="space-y-4">
        <SectionHeading
          title="Diagrams"
          description="Every kind, layout and series type, from handwritten specs — so a renderer bug is distinguishable from a model one."
        />
        <div className="grid gap-4 lg:grid-cols-2">
          {SAMPLE_DIAGRAMS.map((spec) => (
            <div key={spec.id} className="space-y-2">
              <p className="text-eyebrow text-fg-faint uppercase">
                {spec.kind}
                {spec.kind === 'graph' && ` · ${spec.layout}`}
                {spec.steps.length > 0 && ` · ${spec.steps.length} steps`}
              </p>
              <Diagram spec={spec} />
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <SectionHeading title="Toasts" />
        <div className="flex flex-wrap gap-3">
          {(['success', 'info', 'warn', 'danger'] as const).map((tone) => (
            <Button
              key={tone}
              variant="secondary"
              icon={Mic}
              onClick={() =>
                toast({ title: `${tone} toast`, description: 'With a description line.', tone })
              }
            >
              {tone}
            </Button>
          ))}
        </div>
      </section>
    </div>
  )
}
