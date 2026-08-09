import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'motion/react'
import { fadeFast, fadeIn } from './springs'

/**
 * Scroll to top on a real navigation, but not when only the query string
 * changes (filtering a list should not throw the user back to the top).
 */
export function useScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [pathname])
}

interface PageTransitionProps {
  children: React.ReactNode
}

/**
 * `mode="wait"` adds the exit duration to every navigation, so the exit is kept
 * deliberately short — lag on the input path is exactly what this redesign is
 * meant to remove.
 */
export default function PageTransition({ children }: PageTransitionProps) {
  const location = useLocation()
  useScrollToTop()

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0, transition: fadeIn }}
        exit={{ opacity: 0, y: -4, transition: fadeFast }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}
