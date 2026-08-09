import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { Send, Sparkles } from 'lucide-react'
import { useSSE } from '../hooks/useSSE'
import { API_URL } from '../config'
import { Button, Card, Textarea } from './ui'
import { springDefault } from '../motion/springs'
import { cn } from '../lib/cn'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface AIAssistantPanelProps {
  lessonId: string
}

export default function AIAssistantPanel({ lessonId }: AIAssistantPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streamingContent, setStreamingContent] = useState('')
  const [error, setError] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const streamingContentRef = useRef('')

  const { isStreaming, start } = useSSE(`${API_URL}/lessons/${lessonId}/chat`, {
    onChunk: (token) => setStreamingContent((prev) => prev + token),
    onDone: () => {
      setMessages((prev) => {
        const last = prev[prev.length - 1]
        const full = streamingContentRef.current
        if (last?.role === 'assistant' && last.content === '') {
          return [...prev.slice(0, -1), { role: 'assistant', content: full }]
        }
        return [...prev, { role: 'assistant', content: full }]
      })
      setStreamingContent('')
      streamingContentRef.current = ''
    },
    onError: (msg) => setError(msg),
  })

  useEffect(() => {
    streamingContentRef.current = streamingContent
  }, [streamingContent])

  useEffect(() => {
    fetch(`${API_URL}/lessons/${lessonId}/chat/history`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: Array<{ role: string; content: string }>) => {
        setMessages(
          data
            .filter((m) => m.role === 'user' || m.role === 'assistant')
            .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content })),
        )
      })
      .catch(() => {
        /* history is best-effort */
      })
  }, [lessonId])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, streamingContent])

  async function handleSend() {
    const text = input.trim()
    if (!text || isStreaming) return
    setInput('')
    setError(null)
    setStreamingContent('')
    streamingContentRef.current = ''

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text },
      { role: 'assistant', content: '' },
    ])

    await start({
      message: text,
      history: messages.map((m) => ({ role: m.role, content: m.content })),
    })
  }

  return (
    <Card padding="none" className="flex flex-col overflow-hidden">
      <div className="border-hairline flex items-center gap-2 border-b px-4 py-3">
        <Sparkles size={14} className="text-brand-300" aria-hidden="true" />
        <h2 className="text-callout text-fg font-medium">AI tutor</h2>
        {isStreaming && (
          <span className="ml-auto flex gap-1" aria-label="Thinking">
            {[0, 1, 2].map((i) => (
              <motion.span
                key={i}
                className="bg-brand-400 size-1.5 rounded-full"
                animate={{ y: [0, -3, 0] }}
                transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
              />
            ))}
          </span>
        )}
      </div>

      <div
        ref={listRef}
        className="max-h-96 min-h-52 flex-1 space-y-3 overflow-y-auto p-4"
        aria-live="polite"
      >
        {messages.length === 0 && !isStreaming && (
          <p className="text-caption text-fg-subtle pt-6 text-center text-balance">
            Ask anything about this lesson — the tutor answers from the lesson content.
          </p>
        )}

        {messages.map((msg, i) => {
          const isLastAssistant = msg.role === 'assistant' && i === messages.length - 1
          const content = isLastAssistant && isStreaming ? streamingContent : msg.content
          const isUser = msg.role === 'user'

          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6, x: isUser ? 8 : -8 }}
              animate={{ opacity: 1, y: 0, x: 0 }}
              transition={springDefault}
              className={cn('flex', isUser ? 'justify-end' : 'justify-start')}
            >
              <div
                className={cn(
                  'text-callout max-w-[88%] rounded-lg px-3 py-2 leading-relaxed',
                  isUser
                    ? 'bg-brand-500 text-white'
                    : 'bg-surface-raised border-hairline text-fg-muted border',
                )}
              >
                {content ||
                  (msg.role === 'assistant' && isStreaming ? (
                    <span className="text-fg-faint">Thinking…</span>
                  ) : null)}
              </div>
            </motion.div>
          )
        })}
      </div>

      {error && (
        <p role="alert" className="text-caption text-danger px-4 pb-2">
          {error}
        </p>
      )}

      <div className="border-hairline flex items-end gap-2 border-t p-3">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
          rows={2}
          placeholder="Ask a question…"
          aria-label="Ask the tutor a question"
          disabled={isStreaming}
          className="resize-none py-2 text-callout"
        />
        <Button
          size="sm"
          icon={Send}
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
          aria-label="Send"
          className="shrink-0"
        >
          <span className="sr-only">Send</span>
        </Button>
      </div>
    </Card>
  )
}
