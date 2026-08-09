import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { cn } from '../../lib/cn'
import { springSheet, fadeFast } from '../../motion/springs'

type ToastTone = 'success' | 'warn' | 'danger' | 'info'

interface ToastItem {
  id: number
  title: string
  description?: string
  tone: ToastTone
}

interface PushOptions {
  title: string
  description?: string
  tone?: ToastTone
  duration?: number
}

const ToastContext = createContext<((opts: PushOptions) => void) | null>(null)

export function useToast() {
  const push = useContext(ToastContext)
  if (!push) throw new Error('useToast must be used inside <ToastProvider>')
  return push
}

const TONES: Record<ToastTone, { icon: typeof Info; cls: string }> = {
  success: { icon: CheckCircle2, cls: 'text-success' },
  warn: { icon: AlertTriangle, cls: 'text-warn' },
  danger: { icon: XCircle, cls: 'text-danger' },
  info: { icon: Info, cls: 'text-info' },
}

let nextId = 0

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback(
    ({ title, description, tone = 'info', duration = 5000 }: PushOptions) => {
      const id = nextId++
      setItems((prev) => [...prev, { id, title, description, tone }])
      window.setTimeout(() => dismiss(id), duration)
    },
    [dismiss],
  )

  const value = useMemo(() => push, [push])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[100] flex flex-col items-center gap-2 p-4 sm:items-end sm:p-6"
        role="status"
        aria-live="polite"
      >
        <AnimatePresence initial={false}>
          {items.map((t) => {
            const { icon: Icon, cls } = TONES[t.tone]
            return (
              <motion.div
                key={t.id}
                layout
                initial={{ opacity: 0, y: 16, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1, transition: springSheet }}
                exit={{ opacity: 0, scale: 0.96, transition: fadeFast }}
                data-glass
                className="bg-glass border-glass-edge shadow-e3 pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border p-3.5 backdrop-blur-xl"
              >
                <Icon size={18} className={cn('mt-0.5 shrink-0', cls)} aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="text-callout text-fg font-medium">{t.title}</p>
                  {t.description && (
                    <p className="text-caption text-fg-muted mt-0.5">{t.description}</p>
                  )}
                </div>
                <button
                  onClick={() => dismiss(t.id)}
                  aria-label="Dismiss"
                  className="text-fg-faint hover:text-fg -m-1 shrink-0 rounded p-1 transition-colors"
                >
                  <X size={14} />
                </button>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}
