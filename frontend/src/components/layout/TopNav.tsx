import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { AnimatePresence, LayoutGroup, motion } from 'motion/react'
import { Library, Menu, Mic, RotateCcw, X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { springDefault, springSheet, fadeFast } from '../../motion/springs'
import { getReviewQueue } from '../../api'
import Container from './Container'
import Logo from './Logo'

/** Named for their contents rather than as vague umbrellas. */
const LINKS = [
  { to: '/courses', label: 'Library', icon: Library },
  { to: '/review', label: 'Review', icon: RotateCcw },
  { to: '/pronunciation', label: 'Practice', icon: Mic },
] as const

/** Drives the scroll edge effect: no divider until content is actually under the bar. */
function useScrolled(threshold = 8) {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > threshold)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [threshold])
  return scrolled
}

export default function TopNav() {
  const scrolled = useScrolled()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [dueNow, setDueNow] = useState(0)

  // Refresh the due badge whenever the route changes — cheap, and keeps the
  // number honest after a review session.
  useEffect(() => {
    let cancelled = false
    getReviewQueue()
      .then((q) => {
        if (!cancelled) setDueNow(q.due_now)
      })
      .catch(() => {
        /* the badge is decoration; never surface this */
      })
    return () => {
      cancelled = true
    }
  }, [location.pathname])

  useEffect(() => setMenuOpen(false), [location.pathname])

  return (
    <header
      data-glass
      data-scrolled={scrolled || undefined}
      className={cn(
        'bg-glass sticky top-0 z-50 border-b backdrop-blur-xl backdrop-saturate-150',
        'transition-colors duration-[--duration-base]',
        scrolled ? 'border-glass-edge' : 'border-transparent',
      )}
    >
      <Container width="wide">
        <div className="flex h-16 items-center justify-between gap-4">
          <Link
            to="/"
            className="flex items-center gap-2.5 rounded-md"
            aria-label="SuperLearned home"
          >
            <Logo />
            <span className="text-headline text-fg hidden sm:inline">SuperLearned</span>
          </Link>

          <LayoutGroup id="nav">
            <nav className="hidden items-center gap-1 sm:flex" aria-label="Main">
              {LINKS.map(({ to, label }) => (
                <NavLink key={to} to={to} className="relative rounded-md px-3 py-2">
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <motion.span
                          layoutId="nav-active"
                          transition={springDefault}
                          className="bg-surface-raised absolute inset-0 rounded-md"
                        />
                      )}
                      <span
                        className={cn(
                          'text-callout relative transition-colors duration-[--duration-fast]',
                          isActive ? 'text-fg font-medium' : 'text-fg-muted hover:text-fg',
                        )}
                      >
                        {label}
                        {to === '/review' && dueNow > 0 && (
                          <span className="bg-warn/15 text-warn text-eyebrow ml-1.5 rounded-full px-1.5 py-0.5 tabular-nums">
                            {dueNow}
                          </span>
                        )}
                      </span>
                    </>
                  )}
                </NavLink>
              ))}
            </nav>
          </LayoutGroup>

          <button
            onClick={() => setMenuOpen((o) => !o)}
            aria-expanded={menuOpen}
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            className="text-fg-muted hover:text-fg hover:bg-surface-raised -mr-2 rounded-md p-2 transition-colors sm:hidden"
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </Container>

      {/* Enters and exits along the same path. */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1, transition: springSheet }}
            exit={{ height: 0, opacity: 0, transition: fadeFast }}
            className="border-glass-edge overflow-hidden border-t sm:hidden"
          >
            <Container width="wide">
              <nav className="flex flex-col gap-1 py-3" aria-label="Main">
                {LINKS.map(({ to, label, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    className={({ isActive }) =>
                      cn(
                        'text-callout flex min-h-11 items-center gap-3 rounded-md px-3 transition-colors',
                        isActive
                          ? 'bg-surface-raised text-fg font-medium'
                          : 'text-fg-muted hover:text-fg hover:bg-surface-raised',
                      )
                    }
                  >
                    <Icon size={16} aria-hidden="true" />
                    {label}
                    {to === '/review' && dueNow > 0 && (
                      <span className="bg-warn/15 text-warn text-eyebrow ml-auto rounded-full px-1.5 py-0.5 tabular-nums">
                        {dueNow} due
                      </span>
                    )}
                  </NavLink>
                ))}
              </nav>
            </Container>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}
