import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import {
  getMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  setUnauthorizedHandler,
  type AuthUser,
} from '../api'

/**
 * Three states, not a boolean.
 *
 * A boolean reads `false` before the session check resolves, which bounces an
 * already-signed-in user to /login on every hard refresh. `loading` is the
 * state that makes the guard correct.
 */
export type AuthStatus = 'loading' | 'authed' | 'anon'

interface AuthContextValue {
  status: AuthStatus
  user: AuthUser | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)

  // Any 401 anywhere drops us to anonymous, which the route guard reacts to.
  // Registered here because api.ts has no access to React context.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null)
      setStatus('anon')
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  // Resolve the existing cookie once on mount. StrictMode double-invokes this
  // in development, which is harmless: it is an idempotent GET.
  useEffect(() => {
    let cancelled = false
    getMe()
      .then((u) => {
        if (cancelled) return
        setUser(u)
        setStatus('authed')
      })
      .catch(() => {
        if (cancelled) return
        setUser(null)
        setStatus('anon')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const u = await apiLogin(email, password)
    setUser(u)
    setStatus('authed')
  }, [])

  const register = useCallback(async (email: string, password: string, name: string) => {
    const u = await apiRegister(email, password, name)
    setUser(u)
    setStatus('authed')
  }, [])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      // Sign out locally even if the request failed — leaving the UI in a
      // signed-in state after the user asked to leave is the worse outcome.
      setUser(null)
      setStatus('anon')
    }
  }, [])

  return (
    <AuthContext.Provider value={{ status, user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
