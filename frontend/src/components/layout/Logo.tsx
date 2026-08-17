import { cn } from '../../lib/cn'

interface LogoProps {
  size?: number
  className?: string
}

/**
 * Same artwork as public/favicon.svg, so the tab and the nav agree. The tile
 * is a fixed brand mark in both themes — hence --color-logo-*, which hold
 * still, rather than the brand ramp, which retunes for text contrast on light.
 */
export default function Logo({ size = 28, className }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      className={cn('shrink-0', className)}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="logo-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--color-logo-from)" />
          <stop offset="1" stopColor="var(--color-logo-to)" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#logo-grad)" />
      <path
        d="M20.4 11.3c-1-1.1-2.5-1.7-4.3-1.7-2.9 0-4.9 1.5-4.9 3.8 0 2 1.3 3.1 4 3.7l1.5.3c1.5.3 2.1.8 2.1 1.6 0 1-1 1.7-2.6 1.7-1.6 0-2.8-.6-3.6-1.7l-2.2 1.7c1.1 1.6 3 2.5 5.6 2.5 3.2 0 5.4-1.6 5.4-4.1 0-2.1-1.3-3.3-4.1-3.9l-1.5-.3c-1.4-.3-2-.7-2-1.5 0-.9.9-1.5 2.3-1.5 1.3 0 2.4.5 3.1 1.4z"
        fill="#fff"
      />
    </svg>
  )
}
