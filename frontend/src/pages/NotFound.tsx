import { Compass } from 'lucide-react'
import { ButtonLink, EmptyState } from '../components/ui'

export default function NotFound() {
  return (
    <EmptyState
      icon={Compass}
      title="That page doesn't exist"
      description="The link may be out of date, or the course may have been removed."
      action={<ButtonLink to="/courses">Go to library</ButtonLink>}
      secondaryAction={
        <ButtonLink to="/" variant="secondary">
          Start a new course
        </ButtonLink>
      }
    />
  )
}
