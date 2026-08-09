import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { CheckCircle2 } from 'lucide-react'
import { Button } from '../ui'
import { springSheet, fadeFast } from '../../motion/springs'

interface LessonCompleteBarProps {
  title: string
  completed: boolean
  completing: boolean
  onComplete: () => void
}

/**
 * The completion action used to sit inline at the bottom of a long article,
 * effectively below the fold. It now rides along once the reader has committed
 * to the lesson, without covering the header on arrival.
 */
export default function LessonCompleteBar({
  title,
  completed,
  completing,
  onComplete,
}: LessonCompleteBarProps) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    function onScroll() {
      const scrollable = document.body.scrollHeight - window.innerHeight
      if (scrollable <= 0) {
        setVisible(true)
        return
      }
      setVisible(window.scrollY / scrollable > 0.15)
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
    }
  }, [])

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ y: 80, opacity: 0 }}
          animate={{ y: 0, opacity: 1, transition: springSheet }}
          exit={{ y: 80, opacity: 0, transition: fadeFast }}
          data-glass
          className="bg-glass border-glass-edge shadow-e3 fixed inset-x-0 bottom-0 z-40 border-t backdrop-blur-xl"
        >
          <div className="mx-auto flex w-full max-w-6xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
            <p className="text-caption text-fg-subtle hidden min-w-0 flex-1 truncate sm:block">
              {title}
            </p>
            {completed ? (
              <span className="text-callout text-success ml-auto inline-flex items-center gap-2">
                <CheckCircle2 size={16} aria-hidden="true" />
                Completed
              </span>
            ) : (
              <Button
                onClick={onComplete}
                loading={completing}
                icon={CheckCircle2}
                className="ml-auto"
              >
                Mark complete
              </Button>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
