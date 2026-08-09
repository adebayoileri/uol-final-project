import { useEffect, useRef, useState } from 'react'
import Prism from 'prismjs'
import { Check, Copy } from 'lucide-react'
import 'prismjs/components/prism-python'
import 'prismjs/components/prism-javascript'
import 'prismjs/components/prism-typescript'
import 'prismjs/components/prism-bash'
import 'prismjs/components/prism-json'
import 'prismjs/components/prism-sql'
import { cn } from '../lib/cn'

interface Props {
  code: string
  language?: string
  filename?: string
}

function CodeBlock({ code, language = 'python', filename }: Props) {
  const ref = useRef<HTMLElement>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    // Lesson content is LLM-generated, so the fence language is arbitrary.
    if (ref.current && Prism.languages[language]) Prism.highlightElement(ref.current)
  }, [code, language])

  useEffect(() => {
    if (!copied) return
    const id = window.setTimeout(() => setCopied(false), 1600)
    return () => window.clearTimeout(id)
  }, [copied])

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
    } catch {
      /* clipboard may be blocked; silently ignore */
    }
  }

  return (
    <figure className="border-hairline bg-canvas-elevated overflow-hidden rounded-md border">
      <figcaption className="border-hairline flex items-center justify-between gap-3 border-b px-3 py-1.5">
        <span className="text-eyebrow text-fg-faint uppercase">{filename ?? language}</span>
        <button
          onClick={handleCopy}
          className={cn(
            'text-caption inline-flex items-center gap-1.5 rounded px-1.5 py-1 transition-colors',
            copied ? 'text-success' : 'text-fg-faint hover:text-fg',
          )}
          aria-label={copied ? 'Copied' : 'Copy code'}
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </figcaption>
      <pre className="max-h-112 overflow-auto p-4 leading-relaxed">
        <code ref={ref} className={`language-${language}`}>
          {code}
        </code>
      </pre>
    </figure>
  )
}

export default CodeBlock
