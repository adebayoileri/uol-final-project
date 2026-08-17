import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

export type ThemePreference = 'system' | 'light' | 'dark'
export type ResolvedTheme = 'light' | 'dark'

/** Shared with the inline boot script in index.html — keep the two in step. */
export const THEME_STORAGE_KEY = 'theme'

const CANVAS = { light: '#f6f6f9', dark: '#08080d' } as const

interface ThemeContextValue {
  theme: ThemePreference
  resolved: ResolvedTheme
  setTheme: (theme: ThemePreference) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>')
  return ctx
}

function readStored(): ThemePreference {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY)
    if (raw === 'light' || raw === 'dark' || raw === 'system') return raw
  } catch {
    // Safari private mode throws on access; fall through to the default.
  }
  return 'system'
}

function systemTheme(): ResolvedTheme {
  return typeof window !== 'undefined' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Lazy init rather than an effect, so the first render already agrees with
  // what the boot script painted.
  const [theme, setThemeState] = useState<ThemePreference>(readStored)
  const [system, setSystem] = useState<ResolvedTheme>(systemTheme)

  // Follow the OS live while the preference is 'system'. Subscribed
  // unconditionally so switching back to 'system' is immediately correct.
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => setSystem(e.matches ? 'dark' : 'light')
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const resolved: ResolvedTheme = theme === 'system' ? system : theme

  useEffect(() => {
    const root = document.documentElement
    // Absent for 'system', so the CSS media query governs rather than being
    // shadowed by an attribute that merely repeats it.
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)

    // Every theme-color tag, not just the unqualified one. index.html ships a
    // media-qualified pair so the browser chrome is right before JS runs, and
    // the spec returns the FIRST tag whose media matches — which is still the
    // OS preference, not ours. With the OS in dark and the user having chosen
    // light, updating only the unqualified tag would leave the dark one
    // matching and winning, so the chrome would stay dark over a light page.
    // Setting them all makes whichever the browser picks the right answer.
    document
      .querySelectorAll('meta[name="theme-color"]')
      .forEach((tag) => tag.setAttribute('content', CANVAS[resolved]))
  }, [theme, resolved])

  const setTheme = useCallback((next: ThemePreference) => {
    setThemeState(next)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      // Preference simply won't persist; the session still switches.
    }
  }, [])

  const value = useMemo(
    () => ({ theme, resolved, setTheme }),
    [theme, resolved, setTheme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
