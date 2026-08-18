import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, LogOut, Monitor, Moon, Sun } from 'lucide-react'
import { useAuth } from '../../auth/AuthContext'
import { useTheme, type ThemePreference } from '../../theme/ThemeContext'
import { springSheet, fadeFast } from '../../motion/springs'
import { cn } from '../../lib/cn'

const THEME_OPTIONS: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: 'system', label: 'System', icon: Monitor },
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
]

export default function UserMenu() {
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return

    function onKey(e: KeyboardEvent) {
      if (e.key !== 'Escape') return
      setOpen(false)
      // Return focus to where it came from, or the trigger is lost to keyboard users.
      triggerRef.current?.focus()
    }
    function onPointerDown(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }

    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointerDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointerDown)
    }
  }, [open])

  if (!user) return null

  // Accounts predating display names have none, and inventing one from the
  // email local part would be a guess shown back to the person it is about.
  const label = user.name?.trim() || user.email

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="text-fg-muted hover:text-fg hover:bg-surface-raised inline-flex min-h-9 max-w-52 items-center gap-2 rounded-md px-2.5 transition-colors"
      >
        <span className="bg-brand-500 text-on-brand text-caption grid size-6 shrink-0 place-items-center rounded-full font-medium uppercase">
          {label.charAt(0)}
        </span>
        <span className="text-caption hidden truncate sm:inline">{label}</span>
        <ChevronDown
          size={14}
          className={cn('shrink-0 transition-transform duration-[--duration-fast]', open && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1, transition: springSheet }}
            exit={{ opacity: 0, y: -6, scale: 0.98, transition: fadeFast }}
            className="border-border bg-surface-overlay shadow-e3 absolute right-0 z-50 mt-2 w-64 origin-top-right rounded-lg border p-3"
          >
            <div className="mb-3 sm:hidden">
              <p className="text-callout text-fg truncate">{label}</p>
              {user.name && (
                <p className="text-caption text-fg-subtle truncate">{user.email}</p>
              )}
            </div>

            <p className="text-eyebrow text-fg-subtle mb-2 uppercase">Appearance</p>
            <div
              role="radiogroup"
              aria-label="Colour theme"
              className="bg-surface-raised mb-3 flex gap-1 rounded-md p-1"
            >
              {THEME_OPTIONS.map(({ value, label, icon: Icon }) => {
                const active = theme === value
                return (
                  <button
                    key={value}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => setTheme(value)}
                    className={cn(
                      'text-caption flex flex-1 flex-col items-center gap-1 rounded-sm px-2 py-2 font-medium transition-colors duration-[--duration-fast]',
                      active
                        ? 'bg-brand-500 text-on-brand shadow-e1'
                        : 'text-fg-muted hover:text-fg hover:bg-surface-overlay',
                    )}
                  >
                    <Icon size={15} aria-hidden="true" />
                    {label}
                  </button>
                )
              })}
            </div>

            <button
              onClick={() => {
                setOpen(false)
                void logout()
              }}
              role="menuitem"
              className="text-callout text-fg-muted hover:text-fg hover:bg-surface-raised flex min-h-10 w-full items-center gap-2.5 rounded-md px-2.5 transition-colors"
            >
              <LogOut size={15} aria-hidden="true" />
              Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
