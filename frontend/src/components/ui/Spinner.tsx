import { cn } from '../../lib/cn'

const SIZES = {
  sm: 'w-3.5 h-3.5',
  md: 'w-4 h-4',
  lg: 'w-6 h-6',
} as const

interface SpinnerProps {
  size?: keyof typeof SIZES
  className?: string
  label?: string
}

export default function Spinner({ size = 'md', className, label = 'Loading' }: SpinnerProps) {
  return (
    <svg
      className={cn('animate-spin', SIZES[size], className)}
      fill="none"
      viewBox="0 0 24 24"
      role="status"
      aria-label={label}
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  )
}
