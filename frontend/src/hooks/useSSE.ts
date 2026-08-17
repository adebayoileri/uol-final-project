import { useCallback, useLayoutEffect, useRef, useState } from 'react'

interface SSEOptions {
  onChunk: (token: string) => void
  onDone?: () => void
  onError?: (msg: string) => void
}

export function useSSE(url: string, opts: SSEOptions) {
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  // Callers pass a fresh object literal every render, so `opts` can never be a
  // useCallback dep without re-creating `start` on every render.
  const optsRef = useRef(opts)
  useLayoutEffect(() => {
    optsRef.current = opts
  })

  const start = useCallback(
    async (body: object) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      setIsStreaming(true)

      try {
        const res = await fetch(url, {
          credentials: 'include',
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal,
        })
        if (!res.ok) throw new Error(`Server error ${res.status}`)
        if (!res.body) throw new Error('No response body')

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })

          const lines = buf.split('\n')
          buf = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const payload = line.slice(6).trim()
            if (payload === '[DONE]') {
              optsRef.current.onDone?.()
              return
            }
            try {
              const parsed = JSON.parse(payload)
              if (parsed.token) optsRef.current.onChunk(parsed.token)
              if (parsed.error) optsRef.current.onError?.(parsed.error)
            } catch {
              // ignore malformed SSE lines
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          optsRef.current.onError?.(err instanceof Error ? err.message : 'Stream failed')
        }
      } finally {
        setIsStreaming(false)
      }
    },
    [url],
  )

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setIsStreaming(false)
  }, [])

  return { isStreaming, start, abort }
}
