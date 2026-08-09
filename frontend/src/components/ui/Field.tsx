import { forwardRef, useId } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '../../lib/cn'

const CONTROL =
  'block w-full rounded-md border border-border bg-surface-raised px-3 py-2.5 text-callout text-fg ' +
  'placeholder:text-fg-faint transition-colors duration-[--duration-fast] ' +
  'hover:border-border-strong focus:border-brand-500 disabled:cursor-not-allowed disabled:opacity-60 ' +
  'aria-[invalid=true]:border-danger'

interface FieldProps {
  label: string
  hint?: string
  error?: string
  /** Hide the label visually but keep it for assistive tech. */
  srOnlyLabel?: boolean
  className?: string
  children: (props: {
    id: string
    'aria-describedby': string | undefined
    'aria-invalid': boolean | undefined
  }) => React.ReactNode
}

export function Field({ label, hint, error, srOnlyLabel, className, children }: FieldProps) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined

  return (
    <div className={cn('space-y-1.5', className)}>
      <label
        htmlFor={id}
        className={cn('text-callout text-fg-muted block font-medium', srOnlyLabel && 'sr-only')}
      >
        {label}
      </label>
      {children({ id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined })}
      {error ? (
        <p id={errorId} className="text-caption text-danger">
          {error}
        </p>
      ) : (
        hint && (
          <p id={hintId} className="text-caption text-fg-subtle">
            {hint}
          </p>
        )
      )}
    </div>
  )
}

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return <input ref={ref} className={cn(CONTROL, className)} {...rest} />
  },
)

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cn(CONTROL, 'resize-y', className)} {...rest} />
})

export const Select = forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, children, ...rest }, ref) {
  return (
    <div className="relative">
      <select ref={ref} className={cn(CONTROL, 'appearance-none pr-9', className)} {...rest}>
        {children}
      </select>
      <ChevronDown
        size={16}
        className="text-fg-subtle pointer-events-none absolute top-1/2 right-3 -translate-y-1/2"
        aria-hidden="true"
      />
    </div>
  )
})

interface SegmentedProps<T extends string> {
  value: T
  onChange: (value: T) => void
  options: ReadonlyArray<{ value: T; label: string }>
  label: string
  className?: string
}

/** Two or three mutually exclusive choices don't deserve a dropdown. */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  className,
}: SegmentedProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        'inline-flex w-full gap-1 rounded-md border border-border bg-surface-raised p-1',
        className,
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              'flex-1 rounded-sm px-3 py-2 text-callout font-medium transition-colors duration-[--duration-fast]',
              active
                ? 'bg-brand-500 text-white shadow-e1'
                : 'text-fg-muted hover:text-fg hover:bg-surface-overlay',
            )}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
