import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
import Container from '../components/layout/Container'
import { Skeleton } from '../components/ui'

/**
 * Pathless layout route wrapping every authenticated page, so the guard is one
 * insertion rather than eighteen.
 */
export default function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <Container width="wide" className="py-10">
        <div className="space-y-4" aria-busy="true" aria-label="Checking your session">
          <Skeleton variant="title" width="30%" />
          <Skeleton variant="block" height="12rem" />
        </div>
      </Container>
    )
  }

  if (status === 'anon') {
    // `from` lets the login page send the user back where they were, rather
    // than dumping every deep link on the home page.
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <Outlet />
}
