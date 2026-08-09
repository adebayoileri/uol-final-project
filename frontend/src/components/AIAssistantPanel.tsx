import { useEffect, useRef, useState } from 'react'
import { useSSE } from '../hooks/useSSE'
import { API_URL } from '../config'

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

  const { isStreaming, start } = useSSE(`${API_URL}/lessons/${lessonId}/chat`, {
    onChunk: (token) => {
      setStreamingContent((prev) => prev + token)
    },
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

  // Ref for accumulation inside closure
  const streamingContentRef = useRef('')
  useEffect(() => {
    streamingContentRef.current = streamingContent
  }, [streamingContent])

  // Load history on mount
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
      .catch(() => {/* non-critical */})
  }, [lessonId])

  // Scroll to bottom on new messages
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

    const userMsg: Message = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg, { role: 'assistant', content: '' }])

    await start({
      message: text,
      history: messages.map((m) => ({ role: m.role, content: m.content })),
    })
  }

  return (
    <div className="flex flex-col rounded-lg border border-[#2a2a3a] bg-[#111118] overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[#2a2a3a]">
        <span className="text-xs font-medium text-violet-400">AI Tutor</span>
        {isStreaming && (
          <span className="flex gap-0.5">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1 h-1 rounded-full bg-violet-400 animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </span>
        )}
      </div>

      <div
        ref={listRef}
        className="flex-1 overflow-y-auto p-3 space-y-3 min-h-[200px] max-h-[360px]"
      >
        {messages.length === 0 && !isStreaming && (
          <p className="text-xs text-gray-500 text-center pt-4">
            Ask anything about this lesson…
          </p>
        )}

        {messages.map((msg, i) => {
          const isLastAssistant = msg.role === 'assistant' && i === messages.length - 1
          const content = isLastAssistant && isStreaming ? streamingContent : msg.content

          return (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-violet-600 text-white'
                    : 'bg-[#1a1a24] text-gray-300 border border-[#2a2a3a]'
                }`}
              >
                {content || (msg.role === 'assistant' && isStreaming ? (
                  <span className="text-gray-500">Thinking…</span>
                ) : null)}
              </div>
            </div>
          )
        })}
      </div>

      {error && (
        <p className="text-xs text-red-400 px-3 pb-1">{error}</p>
      )}

      <div className="flex gap-2 p-2 border-t border-[#2a2a3a]">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
          rows={2}
          placeholder="Ask a question… (Enter to send)"
          disabled={isStreaming}
          className="flex-1 resize-none rounded-lg border border-[#2a2a3a] bg-[#1a1a24] px-2.5 py-1.5 text-xs text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none disabled:opacity-60"
        />
        <button
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
          className="self-end rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-violet-500 disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  )
}
