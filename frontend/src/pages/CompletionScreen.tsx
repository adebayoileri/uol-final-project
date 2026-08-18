import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import {
  Award,
  BookOpen,
  Brain,
  ChevronDown,
  Download,
  GraduationCap,
  RotateCcw,
  Trophy,
} from 'lucide-react'
import {
  getAchievements,
  getCourse,
  getMastery,
  getReviewQueue,
  type AchievementResponse,
  type CourseResponse,
  type MasteryResponse,
  type ReviewQueueResponse,
  authFetch,
} from '../api'
import MasteryBar from '../components/MasteryBar'
import AchievementCard from '../components/AchievementCard'
import Confetti from '../components/review/Confetti'
import {
  Button,
  ButtonLink,
  Card,
  DashboardSkeleton,
  ErrorState,
  IconBadge,
  SectionHeading,
  StatTile,
  useToast,
} from '../components/ui'
import { listContainer, listItem, springMomentum, springSheet } from '../motion/springs'

const MASTERY_PREVIEW = 6

/** Prefer the server's filename, which names the course rather than its id. */
function filenameFrom(res: Response): string | null {
  const header = res.headers.get('content-disposition')
  const match = header?.match(/filename="([^"]+)"/)
  return match?.[1] ?? null
}

export default function CompletionScreen() {
  const { courseId } = useParams<{ courseId: string }>()
  const toast = useToast()

  const [course, setCourse] = useState<CourseResponse | null>(null)
  const [mastery, setMastery] = useState<MasteryResponse | null>(null)
  const [achievements, setAchievements] = useState<AchievementResponse[]>([])
  const [queue, setQueue] = useState<ReviewQueueResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [showAllMastery, setShowAllMastery] = useState(false)

  const load = useCallback(() => {
    if (!courseId) return
    setLoading(true)
    setError(null)
    Promise.all([
      getCourse(courseId),
      getMastery(courseId),
      getAchievements(),
      getReviewQueue(courseId),
    ])
      .then(([c, m, a, q]) => {
        setCourse(c)
        setMastery(m)
        setAchievements(a)
        setQueue(q)
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [courseId])

  useEffect(load, [load])

  async function handleDownload() {
    if (!courseId) return
    setDownloading(true)
    try {
      const res = await authFetch(`/courses/${courseId}/certificate`)
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.detail ?? `Error ${res.status}`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filenameFrom(res) ?? `certificate-${courseId}.pdf`

      // The anchor must be in the document and the blob URL must outlive the
      // click. Firefox ignores a click on a detached anchor, and Safari aborts
      // a download whose object URL is revoked in the same tick — both of
      // which produce no file while the success toast still fires, so the
      // failure looks like nothing happened at all.
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.setTimeout(() => URL.revokeObjectURL(url), 10_000)

      toast({ title: 'Certificate downloaded', tone: 'success' })
    } catch (err) {
      // Reported as a toast, never through the state that gates the render —
      // a failed download must not wipe the celebration screen.
      toast({
        title: 'Certificate failed',
        description: err instanceof Error ? err.message : undefined,
        tone: 'danger',
      })
    } finally {
      setDownloading(false)
    }
  }

  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={load}
        backTo={`/courses/${courseId}`}
        backLabel="Back to course"
      />
    )
  }
  if (loading) return <DashboardSkeleton tiles={3} />
  if (!course) return null

  const totalLessons = course.modules.reduce((sum, m) => sum + m.lessons.length, 0)
  const unlocked = achievements.filter((a) => a.unlocked)
  const masteryPct = mastery ? Math.round(mastery.overall * 100) : 0
  const concepts = mastery?.concepts ?? []
  const visibleConcepts = showAllMastery ? concepts : concepts.slice(0, MASTERY_PREVIEW)

  return (
    <div className="space-y-10">
      <Card padding="lg" elevation={2} className="relative overflow-hidden text-center">
        <Confetti count={18} />
        <motion.div
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={springMomentum}
          className="relative flex justify-center"
        >
          <IconBadge icon={Trophy} tone="success" size="xl" />
        </motion.div>
        <h1 className="text-display-lg text-fg from-fg via-fg to-gradient-accent mt-6 bg-linear-to-br bg-clip-text text-balance [-webkit-text-fill-color:transparent]">
          Course complete
        </h1>
        <p className="text-body-lg text-fg-muted mt-3">{course.title}</p>
      </Card>

      <motion.div
        variants={listContainer}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 gap-3 sm:grid-cols-3"
      >
        {[
          { icon: GraduationCap, label: 'Lessons completed', value: totalLessons, tone: 'success' as const },
          { icon: Brain, label: 'Knowledge mastery', value: masteryPct, unit: '%', tone: 'brand' as const },
          { icon: RotateCcw, label: 'Cards in rotation', value: queue?.total ?? 0, tone: 'info' as const },
        ].map((t) => (
          <motion.div key={t.label} variants={listItem}>
            <StatTile {...t} countUp />
          </motion.div>
        ))}
      </motion.div>

      {unlocked.length > 0 && (
        <section className="space-y-4">
          <SectionHeading title="Achievements earned" count={unlocked.length} />
          <div className="grid gap-3 sm:grid-cols-2">
            {unlocked.map((a) => (
              <AchievementCard key={a.id} {...a} />
            ))}
          </div>
        </section>
      )}

      {concepts.length > 0 && (
        <section className="space-y-4">
          <SectionHeading
            title="Knowledge mastery"
            description="Derived from FSRS memory stability — 30 days of stability reads as full mastery."
          />
          <Card padding="lg" className="space-y-4">
            {visibleConcepts.map((c, i) => (
              <MasteryBar key={i} name={c.name} mastery={c.mastery} />
            ))}
            <AnimatePresence initial={false}>
              {concepts.length > MASTERY_PREVIEW && (
                <motion.div layout transition={springSheet}>
                  <Button
                    variant="link"
                    size="sm"
                    icon={ChevronDown}
                    iconPosition="right"
                    onClick={() => setShowAllMastery((s) => !s)}
                    className={showAllMastery ? '[&_svg]:rotate-180 [&_svg]:transition-transform' : '[&_svg]:transition-transform'}
                  >
                    {showAllMastery
                      ? 'Show fewer'
                      : `Show all ${concepts.length} concepts`}
                  </Button>
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        </section>
      )}

      {/* Primary first: hierarchy and DOM order now agree. */}
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <ButtonLink to={`/courses/${courseId}/review`} size="lg" icon={RotateCcw}>
          Review cards
        </ButtonLink>
        <Button
          variant="secondary"
          size="lg"
          icon={Download}
          onClick={handleDownload}
          loading={downloading}
        >
          Download certificate
        </Button>
        <ButtonLink to={`/courses/${courseId}`} variant="ghost" size="lg" icon={Award}>
          Back to course
        </ButtonLink>
        <ButtonLink to="/" variant="ghost" size="lg" icon={BookOpen}>
          Start a new course
        </ButtonLink>
      </div>
    </div>
  )
}
