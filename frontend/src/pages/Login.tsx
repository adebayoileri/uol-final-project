import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { LogIn, UserPlus } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { Button, Card, ErrorState, Field, Input } from '../components/ui'
import Logo from '../components/layout/Logo'
import { riseIn } from '../motion/springs'

interface Props {
  mode: 'login' | 'register'
}

export default function Login({ mode }: Props) {
  const { status, login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isRegister = mode === 'register'
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/'

  // Already signed in: never show the form. Covers hitting /login directly
  // with a live session.
  if (status === 'authed') return <Navigate to={from} replace />

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await (isRegister ? register(email, password) : login(email, password))
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <motion.div variants={riseIn} initial="hidden" animate="show">
        <div className="mb-8 flex flex-col items-center text-center">
          <Logo size={40} />
          <h1 className="text-display-lg text-fg mt-4">
            {isRegister ? 'Create your account' : 'Welcome back'}
          </h1>
          <p className="text-body text-fg-muted mt-2">
            {isRegister
              ? 'Your courses, review schedule and progress are private to you.'
              : 'Sign in to pick up where you left off.'}
          </p>
        </div>

        <Card padding="lg" elevation={2}>
          <form onSubmit={handleSubmit} className="space-y-5">
            <Field label="Email">
              {(p) => (
                <Input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  {...p}
                />
              )}
            </Field>

            <Field
              label="Password"
              hint={isRegister ? 'At least 8 characters.' : undefined}
            >
              {(p) => (
                <Input
                  type="password"
                  autoComplete={isRegister ? 'new-password' : 'current-password'}
                  required
                  minLength={isRegister ? 8 : undefined}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  {...p}
                />
              )}
            </Field>

            {error && <ErrorState inline message={error} />}

            <Button
              type="submit"
              size="lg"
              fullWidth
              loading={busy}
              icon={isRegister ? UserPlus : LogIn}
            >
              {isRegister ? 'Create account' : 'Sign in'}
            </Button>
          </form>
        </Card>

        <p className="text-callout text-fg-muted mt-6 text-center">
          {isRegister ? 'Already have an account? ' : "Don't have an account? "}
          <Link
            to={isRegister ? '/login' : '/register'}
            className="text-brand-300 hover:text-brand-200 underline underline-offset-4"
          >
            {isRegister ? 'Sign in' : 'Create one'}
          </Link>
        </p>
      </motion.div>
    </div>
  )
}
