import { forwardRef } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'
import { springSnappy } from '../../motion/springs'
import Spinner from './Spinner'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'link'
type Size = 'sm' | 'md' | 'lg'

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-brand-500 text-white shadow-e1 hover:bg-brand-400 active:bg-brand-600 disabled:hover:bg-brand-500',
  secondary:
    'bg-surface-raised text-fg border border-border hover:border-border-strong hover:bg-surface-overlay disabled:hover:border-border',
  ghost: 'text-fg-muted hover:text-fg hover:bg-surface-raised',
  danger: 'bg-danger/15 text-danger border border-danger/40 hover:bg-danger/25',
  link: 'text-brand-300 underline underline-offset-4 hover:text-brand-200 px-0 py-0',
}

const SIZES: Record<Size, string> = {
  sm: 'text-caption px-3 min-h-9 gap-1.5',
  md: 'text-callout px-4 min-h-11 gap-2',
  lg: 'text-body px-5 min-h-12 gap-2',
}

const ICON_SIZE: Record<Size, number> = { sm: 14, md: 16, lg: 18 }

interface BaseProps {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: LucideIcon
  iconPosition?: 'left' | 'right'
  fullWidth?: boolean
  className?: string
  children?: React.ReactNode
}

type ButtonProps = BaseProps &
  Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, keyof BaseProps | 'ref'> & { to?: never }

type LinkProps = BaseProps & { to: string; replace?: boolean }

function classesFor({
  variant = 'primary',
  size = 'md',
  fullWidth,
  className,
}: Pick<BaseProps, 'variant' | 'size' | 'fullWidth' | 'className'>) {
  return cn(
    'relative inline-flex items-center justify-center rounded-md font-medium select-none',
    'transition-colors duration-[--duration-fast]',
    'disabled:cursor-not-allowed disabled:opacity-50',
    'aria-disabled:cursor-not-allowed aria-disabled:opacity-50',
    variant !== 'link' && SIZES[size],
    VARIANTS[variant],
    fullWidth && 'w-full',
    className,
  )
}

/**
 * `whileTap` fires on pointer-down rather than on click, so the press reads as
 * instant. Loading swaps the label in place at a fixed width so the button
 * never changes size mid-interaction.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'primary',
    size = 'md',
    loading = false,
    icon: Icon,
    iconPosition = 'left',
    fullWidth,
    className,
    children,
    disabled,
    ...rest
  },
  ref,
) {
  const iconSize = ICON_SIZE[size]
  return (
    <motion.button
      ref={ref}
      whileTap={disabled || loading ? undefined : { scale: 0.97 }}
      transition={springSnappy}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={classesFor({ variant, size, fullWidth, className })}
      {...(rest as React.ComponentProps<typeof motion.button>)}
    >
      <span
        className={cn(
          'inline-flex items-center',
          size === 'sm' ? 'gap-1.5' : 'gap-2',
          loading && 'invisible',
        )}
      >
        {Icon && iconPosition === 'left' && <Icon size={iconSize} aria-hidden="true" />}
        {children}
        {Icon && iconPosition === 'right' && <Icon size={iconSize} aria-hidden="true" />}
      </span>
      {loading && (
        <span className="absolute inset-0 grid place-items-center">
          <Spinner size={size === 'lg' ? 'md' : 'sm'} />
        </span>
      )}
    </motion.button>
  )
})

/** Same visual language as Button, but renders a router Link. */
export function ButtonLink({
  variant = 'primary',
  size = 'md',
  icon: Icon,
  iconPosition = 'left',
  fullWidth,
  className,
  children,
  to,
  replace,
}: LinkProps) {
  const iconSize = ICON_SIZE[size]
  return (
    <Link to={to} replace={replace} className={classesFor({ variant, size, fullWidth, className })}>
      <span className={cn('inline-flex items-center', size === 'sm' ? 'gap-1.5' : 'gap-2')}>
        {Icon && iconPosition === 'left' && <Icon size={iconSize} aria-hidden="true" />}
        {children}
        {Icon && iconPosition === 'right' && <Icon size={iconSize} aria-hidden="true" />}
      </span>
    </Link>
  )
}

export default Button
