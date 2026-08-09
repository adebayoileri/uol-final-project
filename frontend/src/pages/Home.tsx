import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { ArrowRight, BookOpen, Flame, Sparkles, Wand2 } from 'lucide-react'
import { createCourse, getCourses, type CourseRequest, type CourseSummaryResponse } from '../api'
import {
  Button,
  ButtonLink,
  Card,
  ErrorState,
  Field,
  Input,
  ProgressBar,
  Segmented,
  Skeleton,
  Textarea,
} from '../components/ui'
import { listContainer, listItem, riseIn, springDefault } from '../motion/springs'

/**
 * Course generation is a multi-second LLM call. Honest stage labels beat a
 * fabricated percentage, and beat the previous behaviour — a disabled button
 * with an ellipsis and nothing else.
 */
const STAGES = [
  'Understanding your goal…',
  'Designing the module structure…',
  'Writing lesson content…',
  'Setting objectives…',
  'Almost there…',
] as const

const HOW_IT_WORKS = [
  { icon: Wand2, title: 'Describe a goal', body: 'Plain language. No syllabus required.' },
  { icon: BookOpen, title: 'Get a real course', body: 'Modules, lessons, objectives, questions.' },
  { icon: Flame, title: 'Keep it', body: 'FSRS schedules reviews before you forget.' },
]

export default function Home() {
  const navigate = useNavigate()
  const [courses, setCourses] = useState<CourseSummaryResponse[] | null>(null)
  const [goal, setGoal] = useState('')
  const [duration, setDuration] = useState<CourseRequest['duration']>('short_term')
  const [category, setCategory] = useState('')
  const [loading, setLoading] = useState(false)
  const [stage, setStage] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const stageTimer = useRef<number | null>(null)

  useEffect(() => {
    getCourses()
      .then(setCourses)
      .catch(() => setCourses([]))
  }, [])

  useEffect(() => {
    if (!loading) {
      if (stageTimer.current) window.clearInterval(stageTimer.current)
      setStage(0)
      return
    }
    stageTimer.current = window.setInterval(() => {
      setStage((s) => Math.min(s + 1, STAGES.length - 1))
    }, 2500)
    return () => {
      if (stageTimer.current) window.clearInterval(stageTimer.current)
    }
  }, [loading])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const course = await createCourse({ goal, duration, category })
      navigate(`/courses/${course.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate course.')
    } finally {
      setLoading(false)
    }
  }

  const recent = (courses ?? []).slice(0, 2)
  const hasCourses = recent.length > 0

  return (
    <div className="relative">
      {/* Static glow. A slowly looping full-viewport background would be a
          vestibular hazard, so it does not animate. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 -top-32 -z-10 h-72 bg-[radial-gradient(60%_100%_at_50%_0%,var(--color-brand-700)_0%,transparent_70%)] opacity-25 blur-3xl"
      />

      <motion.div
        variants={listContainer}
        initial="hidden"
        animate="show"
        className="mx-auto max-w-3xl text-center"
      >
        <motion.p
          variants={listItem}
          className="text-eyebrow text-brand-300 mb-4 inline-flex items-center gap-1.5 uppercase"
        >
          <Sparkles size={12} aria-hidden="true" />
          Local-first · Llama · FSRS
        </motion.p>
        <motion.h1
          variants={listItem}
          className="text-display-xl md:text-display-2xl text-balance bg-linear-to-br from-fg via-fg to-brand-300 bg-clip-text text-transparent"
        >
          {hasCourses ? 'Start a new goal' : 'Learn anything, and actually keep it'}
        </motion.h1>
        <motion.p variants={listItem} className="text-body-lg text-fg-muted mx-auto mt-5 max-w-xl">
          Describe what you want to learn. You get a structured course with lessons, questions and a
          spaced-repetition schedule that brings each idea back before you forget it.
        </motion.p>
      </motion.div>

      <div className="mt-12 grid gap-6 lg:grid-cols-12">
        <motion.div
          variants={riseIn}
          initial="hidden"
          animate="show"
          className="lg:col-span-7"
        >
          <Card elevation={3} padding="lg">
            <form onSubmit={handleSubmit} className="space-y-5">
              <Field label="What do you want to learn?" hint="Be specific — it shapes the whole course.">
                {(p) => (
                  <Textarea
                    required
                    minLength={10}
                    maxLength={1000}
                    rows={4}
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    placeholder="e.g. Learn Python to automate repetitive tasks at work"
                    {...p}
                  />
                )}
              </Field>

              <Field label="Category" hint="Drives question style — Python courses get fill-in-the-blank code.">
                {(p) => (
                  <Input
                    required
                    minLength={2}
                    maxLength={100}
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    placeholder="e.g. Programming, Spanish, Statistics"
                    {...p}
                  />
                )}
              </Field>

              <div className="space-y-1.5">
                <span className="text-callout text-fg-muted block font-medium">Depth</span>
                <Segmented
                  label="Depth"
                  value={duration}
                  onChange={setDuration}
                  options={[
                    { value: 'short_term', label: 'Short term' },
                    { value: 'long_term', label: 'Long term' },
                  ]}
                />
              </div>

              {error && <ErrorState inline message={error} />}

              <div className="space-y-3 pt-1">
                <Button type="submit" size="lg" icon={Sparkles} loading={loading} fullWidth>
                  Generate course
                </Button>
                {loading && (
                  <motion.p
                    key={stage}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={springDefault}
                    className="text-caption text-fg-subtle text-center"
                    aria-live="polite"
                  >
                    {STAGES[stage]}
                  </motion.p>
                )}
              </div>
            </form>
          </Card>
        </motion.div>

        <div className="space-y-4 lg:col-span-5">
          {loading ? (
            <Card padding="lg" className="space-y-4">
              <Skeleton width="9rem" />
              <Skeleton variant="block" height="3rem" />
              <Skeleton variant="block" height="3rem" />
              <Skeleton variant="block" height="3rem" />
            </Card>
          ) : courses === null ? (
            <Card padding="lg" className="space-y-3">
              <Skeleton width="8rem" />
              <Skeleton variant="block" height="4rem" />
            </Card>
          ) : hasCourses ? (
            <>
              <h2 className="text-headline text-fg">Continue where you left off</h2>
              <motion.div
                variants={listContainer}
                initial="hidden"
                animate="show"
                className="space-y-3"
              >
                {recent.map((c) => {
                  const { total_lessons, completed_lessons, due_now } = c.progress_summary
                  const pct = total_lessons ? completed_lessons / total_lessons : 0
                  return (
                    <motion.div key={c.id} variants={listItem}>
                      <Card interactive padding="none">
                        <Link to={`/courses/${c.id}`} className="group block px-4 py-4">
                          <div className="flex items-start justify-between gap-3">
                            <span className="text-callout text-fg line-clamp-2 font-medium">
                              {c.title}
                            </span>
                            <ArrowRight
                              size={16}
                              className="text-fg-faint mt-0.5 shrink-0 transition-transform duration-[--duration-fast] group-hover:translate-x-0.5"
                              aria-hidden="true"
                            />
                          </div>
                          <ProgressBar value={pct} size="xs" className="mt-3" />
                          <div className="text-caption text-fg-subtle mt-2 flex items-center gap-2">
                            <span className="tabular-nums">
                              {completed_lessons}/{total_lessons} lessons
                            </span>
                            {due_now > 0 && (
                              <span className="text-warn inline-flex items-center gap-1">
                                <Flame size={11} aria-hidden="true" />
                                {due_now} due
                              </span>
                            )}
                          </div>
                        </Link>
                      </Card>
                    </motion.div>
                  )
                })}
              </motion.div>
              <ButtonLink to="/courses" variant="secondary" fullWidth icon={BookOpen}>
                All courses
              </ButtonLink>
            </>
          ) : (
            <>
              <h2 className="text-headline text-fg">How it works</h2>
              <div className="space-y-3">
                {HOW_IT_WORKS.map(({ icon: Icon, title, body }, i) => (
                  <Card key={title} padding="md" className="flex items-start gap-3">
                    <span className="bg-brand-500/12 text-brand-300 text-caption grid size-7 shrink-0 place-items-center rounded-md font-medium tabular-nums">
                      {i + 1}
                    </span>
                    <span className="min-w-0">
                      <span className="text-callout text-fg flex items-center gap-1.5 font-medium">
                        <Icon size={14} className="text-brand-300" aria-hidden="true" />
                        {title}
                      </span>
                      <span className="text-caption text-fg-subtle mt-0.5 block">{body}</span>
                    </span>
                  </Card>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
