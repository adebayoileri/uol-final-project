import { cn } from '../../lib/cn'

/**
 * Reading surfaces stay narrow; dashboards go wide. Previously every page —
 * including the lesson reader and the dashboards — shared one 768px column.
 */
export const WIDTHS = {
  prose: 'max-w-[46rem]',
  narrow: 'max-w-2xl',
  medium: 'max-w-4xl',
  wide: 'max-w-6xl',
  full: 'max-w-[90rem]',
} as const

export type ContainerWidth = keyof typeof WIDTHS

interface ContainerProps {
  width?: ContainerWidth
  className?: string
  children: React.ReactNode
}

export default function Container({ width = 'wide', className, children }: ContainerProps) {
  return (
    <div className={cn('mx-auto w-full px-4 sm:px-6 lg:px-8', WIDTHS[width], className)}>
      {children}
    </div>
  )
}
