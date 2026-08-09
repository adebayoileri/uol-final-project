type CalloutVariant = 'note' | 'warning'

interface CalloutProps {
  variant: CalloutVariant
  children: React.ReactNode
}

const STYLES: Record<CalloutVariant, { wrapper: string; icon: string }> = {
  note: {
    wrapper: 'bg-blue-900/20 border-blue-800 text-blue-200',
    icon: 'ℹ',
  },
  warning: {
    wrapper: 'bg-amber-900/20 border-amber-700 text-amber-200',
    icon: '⚠',
  },
}

export default function Callout({ variant, children }: CalloutProps) {
  const { wrapper, icon } = STYLES[variant]
  return (
    <div className={`flex gap-2 rounded-lg border p-3 text-sm my-3 ${wrapper}`}>
      <span className="shrink-0 font-bold">{icon}</span>
      <div className="flex-1">{children}</div>
    </div>
  )
}
