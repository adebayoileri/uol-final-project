import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Clock, Target } from 'lucide-react'
import {
  completeLesson,
  generateQuestions,
  getCourse,
  getLessonDetail,
  type LessonDetailResponse,
} from '../api'
import AudioPlayer from '../components/AudioPlayer'
import AIAssistantPanel from '../components/AIAssistantPanel'
import LessonBody from '../components/lesson/LessonBody'
import LessonCompleteBar from '../components/lesson/LessonCompleteBar'
import QuestionDeck, { GenerateQuestionsPrompt } from '../components/lesson/QuestionDeck'
import { Badge, Card, ErrorState, IconBadge, LessonSkeleton, useToast } from '../components/ui'

export default function LessonView() {
  const { courseId, lessonId } = useParams<{ courseId: string; lessonId: string }>()
  const navigate = useNavigate()
  const toast = useToast()

  const [lesson, setLesson] = useState<LessonDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [completing, setCompleting] = useState(false)

  const [qIndex, setQIndex] = useState<number>(() => {
    const saved = lessonId ? localStorage.getItem(`lesson-${lessonId}-qi`) : null
    return saved ? parseInt(saved, 10) : 0
  })

  const fetchLesson = useCallback(() => {
    if (!courseId || !lessonId) return Promise.resolve()
    return getLessonDetail(courseId, lessonId)
      .then(setLesson)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [courseId, lessonId])

  useEffect(() => {
    fetchLesson()
  }, [fetchLesson])

  useEffect(() => {
    if (lessonId) localStorage.setItem(`lesson-${lessonId}-qi`, String(qIndex))
  }, [lessonId, qIndex])

  async function handleGenerate() {
    if (!lessonId) return
    setGenerating(true)
    try {
      await generateQuestions(lessonId)
      // Deliberately does NOT set `loading` — that would unmount the page and
      // throw away the reader's scroll position.
      await fetchLesson()
      setQIndex(0)
      toast({ title: 'Questions ready', tone: 'success' })
    } catch (err) {
      toast({
        title: 'Could not generate questions',
        description: err instanceof Error ? err.message : undefined,
        tone: 'danger',
      })
    } finally {
      setGenerating(false)
    }
  }

  async function handleComplete() {
    if (!lessonId || !courseId) return
    setCompleting(true)
    try {
      await completeLesson(lessonId)
      const updatedCourse = await getCourse(courseId)
      const allDone = updatedCourse.modules.every((m) =>
        m.lessons.every((l) => l.completed_at !== null),
      )
      navigate(allDone ? `/courses/${courseId}/complete` : `/courses/${courseId}`)
    } catch (err) {
      toast({
        title: 'Could not mark complete',
        description: err instanceof Error ? err.message : undefined,
        tone: 'danger',
      })
    } finally {
      setCompleting(false)
    }
  }

  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          setError(null)
          setLoading(true)
          fetchLesson()
        }}
        backTo={`/courses/${courseId}`}
        backLabel="Back to course"
      />
    )
  }
  if (loading) return <LessonSkeleton />
  if (!lesson) return null

  return (
    <>
      <div className="grid gap-10 xl:grid-cols-[minmax(0,46rem)_20rem] xl:justify-center">
        <article className="min-w-0 space-y-10 pb-28">
          <header className="space-y-4">
            <nav aria-label="Breadcrumb">
              <Link
                to={`/courses/${courseId}`}
                className="text-callout text-fg-subtle hover:text-fg -ml-2 inline-flex min-h-11 items-center gap-1.5 rounded-md px-2 transition-colors"
              >
                <ArrowLeft size={16} aria-hidden="true" />
                Back to course
              </Link>
            </nav>

            <div className="flex flex-wrap items-start justify-between gap-4">
              <h1 className="text-display-lg text-fg text-balance">{lesson.title}</h1>
              <Badge icon={Clock} className="mt-2 shrink-0">
                {lesson.duration_minutes} min
              </Badge>
            </div>

            <AudioPlayer lessonId={lesson.id} />
          </header>

          {lesson.objectives.length > 0 && (
            <Card padding="lg">
              <h2 className="text-headline text-fg mb-3 flex items-center gap-2.5">
                <IconBadge icon={Target} tone="brand" size="sm" />
                What you'll be able to do
              </h2>
              <ul className="space-y-2">
                {lesson.objectives.map((obj) => (
                  <li key={obj.id} className="text-body text-fg-muted flex gap-2.5">
                    <span className="bg-brand-400 mt-2.5 size-1.5 shrink-0 rounded-full" />
                    {obj.description}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {lesson.description && <LessonBody description={lesson.description} />}

          <section className="space-y-4">
            <h2 className="text-headline text-fg">
              Practice
              {lesson.questions.length > 0 && (
                <span className="text-fg-faint ml-2 tabular-nums">{lesson.questions.length}</span>
              )}
            </h2>
            {lesson.questions.length === 0 ? (
              <GenerateQuestionsPrompt onGenerate={handleGenerate} generating={generating} />
            ) : (
              <QuestionDeck
                questions={lesson.questions}
                index={Math.min(qIndex, lesson.questions.length - 1)}
                onIndexChange={setQIndex}
                onError={(message) => toast({ title: message, tone: 'danger' })}
              />
            )}
          </section>

          {/* Below xl the tutor sits inline, as it did before. */}
          <div className="xl:hidden">
            <AIAssistantPanel lessonId={lesson.id} />
          </div>
        </article>

        <aside className="hidden xl:sticky xl:top-20 xl:block xl:self-start">
          <AIAssistantPanel lessonId={lesson.id} />
        </aside>
      </div>

      <LessonCompleteBar
        title={lesson.title}
        completed={lesson.completed_at !== null}
        completing={completing}
        onComplete={handleComplete}
      />
    </>
  )
}
