import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { ArrowRight, BookOpen, Flame, Sparkles, Wand2 } from 'lucide-react'
import { createCourse, getCategories, getCourses, suggestCategory, type CategoryOption, type CategorySuggestion, type CourseRequest, type CourseSummaryResponse } from '../api'
import {
  Button,
  ButtonLink,
  Card,
  ErrorState,
  Field,
  Input,
  ProgressBar,
  Segmented,
  Select,
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

/**
 * Category selects a value the generator branches on, so it is a fixed list
 * rather than a text box: "Programming" and "Python" read the same to a person
 * and mean different things to the question generator. The list is fetched from
 * the server, which is also what validates it, so the two cannot disagree.
 */
const AUTO_MODE = 'auto'
const OTHER_MODE = 'other'
const MIN_GOAL_FOR_DETECTION = 10
const DETECT_DEBOUNCE_MS = 600

/** Group options for `<optgroup>`, preserving the order the server sent. */
function groupCategories(options: CategoryOption[]): Array<[string, CategoryOption[]]> {
  const groups = new Map<string, CategoryOption[]>()
  for (const option of options) {
    const bucket = groups.get(option.group)
    if (bucket) bucket.push(option)
    else groups.set(option.group, [option])
  }
  return [...groups.entries()]
}

export default function Home() {
  const navigate = useNavigate()
  const [courses, setCourses] = useState<CourseSummaryResponse[] | null>(null)
  const [goal, setGoal] = useState('')
  const [duration, setDuration] = useState<CourseRequest['duration']>('short_term')
  const [loading, setLoading] = useState(false)
  const [stage, setStage] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const stageTimer = useRef<number | null>(null)

  // Category state. `categoryMode` is what the learner picked; `customCategory`
  // only matters under "Other".
  const [categoryMode, setCategoryMode] = useState<string>(AUTO_MODE)
  const [customCategory, setCustomCategory] = useState('')
  const [categories, setCategories] = useState<CategoryOption[] | null>(null)
  // A detection, tagged with the goal it was run against. Compare rather than
  // reset: clearing on every keystroke would flicker, and not clearing at all
  // would let a stale answer be submitted for a goal it was never about.
  const [detection, setDetection] = useState<{
    forGoal: string
    suggestion: CategorySuggestion | null
    pending: boolean
  } | null>(null)

  useEffect(() => {
    getCourses()
      .then(setCourses)
      .catch(() => setCourses([]))
  }, [])

  useEffect(() => {
    getCategories()
      .then(setCategories)
      .catch(() => setCategories([]))
  }, [])

  const goalKey = goal.trim()
  // The vocabulary failed to load. Fall back to the free-text box it replaced:
  // an empty dropdown would make the form impossible to submit, which is a
  // worse outcome than a category the server has to interpret from the goal.
  const hasPicker = (categories?.length ?? 0) > 0
  const groupedCategories = groupCategories(categories ?? [])
  const activeDetection = detection?.forGoal === goalKey ? detection : null
  const suggestion = activeDetection?.suggestion ?? null
  const detecting = activeDetection?.pending ?? false

  useEffect(() => {
    if (!hasPicker || categoryMode !== AUTO_MODE) return
    if (goalKey.length < MIN_GOAL_FOR_DETECTION) {
      setDetection(null)
      return
    }

    let cancelled = false
    const controller = new AbortController()
    setDetection({ forGoal: goalKey, suggestion: null, pending: true })

    const timer = window.setTimeout(() => {
      suggestCategory(goalKey, controller.signal)
        .then((result) => {
          if (cancelled) return
          setDetection({ forGoal: goalKey, suggestion: result, pending: false })
        })
        .catch(() => {
          // Not an error worth a banner: the server resolves the category
          // anyway if we submit without one. The hint says so.
          if (cancelled) return
          setDetection({ forGoal: goalKey, suggestion: null, pending: false })
        })
    }, DETECT_DEBOUNCE_MS)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [goalKey, categoryMode, hasPicker])

  /** The category sent to the server. `AUTO` means "you decide". */
  const submittedCategory = !hasPicker
    ? customCategory.trim()
    : categoryMode === AUTO_MODE
      ? (suggestion?.value ?? AUTO_MODE)
      : categoryMode === OTHER_MODE
        ? customCategory.trim()
        : categoryMode

  const selectedNote = categories?.find((c) => c.value === categoryMode)?.note

  /**
   * One line under the control, doing three jobs: saying what the field affects,
   * reporting what Auto decided, and flagging when that decision was a guess.
   */
  const categoryHint = (() => {
    if (!hasPicker) return 'Shapes question style, narration voice and diagrams.'
    if (categoryMode === AUTO_MODE) {
      if (detecting) return 'Reading your goal\u2026'
      if (suggestion) {
        const lead = suggestion.source === 'model' ? 'Detected' : 'Best guess'
        return suggestion.note
          ? `${lead}: ${suggestion.label} \u2014 ${suggestion.note}`
          : `${lead}: ${suggestion.label}`
      }
      return goalKey.length >= MIN_GOAL_FOR_DETECTION
        ? "Couldn't read a category from that \u2014 we'll match it when you generate."
        : 'Describe your goal and we\u2019ll choose the category for you.'
    }
    if (categoryMode === OTHER_MODE) return 'Kept exactly as you type it.'
    return selectedNote ?? 'Shapes question style, narration voice and diagrams.'
  })()

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
      const course = await createCourse({ goal, duration, category: submittedCategory })
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
        className="pointer-events-none absolute inset-x-0 -top-32 -z-10 h-72 bg-[radial-gradient(60%_100%_at_50%_0%,var(--color-hero-glow)_0%,transparent_70%)] opacity-25 blur-3xl"
      />

      <motion.div
        variants={listContainer}
        initial="hidden"
        animate="show"
        className="mx-auto max-w-3xl text-center"
      >
        <motion.h1
          variants={listItem}
          className="text-display-xl md:text-display-2xl text-balance text-fg bg-linear-to-br from-fg via-fg to-gradient-accent bg-clip-text [-webkit-text-fill-color:transparent]"
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

              <Field
                label="Category"
                hint={categoryHint}
                hintLive
              >
                {(p) =>
                  hasPicker ? (
                    <div className="space-y-2">
                      <Select
                        value={categoryMode}
                        onChange={(e) => setCategoryMode(e.target.value)}
                        {...p}
                      >
                        <option value={AUTO_MODE}>Auto — detect from my goal</option>
                        {groupedCategories.map(([group, options]) => (
                          <optgroup key={group} label={group}>
                            {options.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </optgroup>
                        ))}
                        <option value={OTHER_MODE}>Other — type my own</option>
                      </Select>
                      {categoryMode === OTHER_MODE && (
                        <Input
                          required
                          minLength={2}
                          maxLength={100}
                          aria-label="Your category"
                          value={customCategory}
                          onChange={(e) => setCustomCategory(e.target.value)}
                          placeholder="e.g. Marine Biology"
                        />
                      )}
                    </div>
                  ) : (
                    <Input
                      required
                      minLength={2}
                      maxLength={100}
                      value={customCategory}
                      onChange={(e) => setCustomCategory(e.target.value)}
                      placeholder="e.g. Programming, Spanish, Statistics"
                      {...p}
                    />
                  )
                }
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
