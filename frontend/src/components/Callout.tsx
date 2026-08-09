import { AlertTriangle, Info, Lightbulb, XOctagon } from 'lucide-react'
import { cn } from '../lib/cn'

type CalloutVariant = 'note' | 'warning' | 'tip' | 'danger'

const STYLES: Record<CalloutVariant, { wrapper: string; icon: typeof Info; iconCls: string }> = {
  note: { wrapper: 'border-info/35 bg-info/8', icon: Info, iconCls: 'text-info' },
  tip: { wrapper: 'border-success/35 bg-success/8', icon: Lightbulb, iconCls: 'text-success' },
  warning: { wrapper: 'border-warn/35 bg-warn/8', icon: AlertTriangle, iconCls: 'text-warn' },
  danger: { wrapper: 'border-danger/35 bg-danger/8', icon: XOctagon, iconCls: 'text-danger' },
}

interface CalloutProps {
  variant?: CalloutVariant
  children: React.ReactNode
}

export default function Callout({ variant = 'note', children }: CalloutProps) {
  const { wrapper, icon: Icon, iconCls } = STYLES[variant]
  return (
    <div className={cn('flex gap-3 rounded-md border p-4', wrapper)}>
      <Icon size={17} className={cn('mt-0.5 shrink-0', iconCls)} aria-hidden="true" />
      <div className="text-callout text-fg-muted min-w-0 flex-1 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
        {children}
      </div>
    </div>
  )
}
