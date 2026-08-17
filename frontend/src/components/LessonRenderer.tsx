import { Fragment, cloneElement, isValidElement } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import CodeBlock from './CodeBlock'
import Callout from './Callout'

// KaTeX styles must be available — imported in index.html or via a global CSS import.
// The bundle ships the fonts; we only need the CSS entrypoint here.
import 'katex/dist/katex.min.css'

interface LessonRendererProps {
  content: string
}

function detectCalloutVariant(text: string): 'note' | 'warning' | null {
  const normalised = text.trim().toUpperCase()
  if (normalised.startsWith('[!NOTE]')) return 'note'
  if (normalised.startsWith('[!WARNING]')) return 'warning'
  return null
}

const MARKER_RE = /^\s*\[!(?:NOTE|WARNING)\]\s*/i

/**
 * Remove the `[!NOTE]` / `[!WARNING]` marker from the first string leaf while
 * leaving the rest of the tree intact, so inline markdown (bold, links, code)
 * inside a callout survives. Flattening to a plain string would destroy it.
 */
function stripLeadingMarker(node: React.ReactNode): React.ReactNode {
  let done = false

  function walk(n: React.ReactNode): React.ReactNode {
    if (done) return n

    if (typeof n === 'string') {
      if (!n.trim()) return n
      done = true
      return n.replace(MARKER_RE, '')
    }

    if (Array.isArray(n)) return n.map((child, i) => <Fragment key={i}>{walk(child)}</Fragment>)

    if (isValidElement(n)) {
      const el = n as React.ReactElement<{ children?: React.ReactNode }>
      if (el.props.children == null) return n
      return cloneElement(el, { children: walk(el.props.children) })
    }

    return n
  }

  return walk(node)
}

export default function LessonRenderer({ content }: LessonRendererProps) {
  return (
    <div className="prose-lesson">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // Code blocks → existing CodeBlock with Prism
          code({ node: _node, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            const isBlock = !!match
            if (isBlock) {
              return (
                <CodeBlock
                  code={String(children).replace(/\n$/, '')}
                  language={match[1]}
                />
              )
            }
            return (
              <code
                className="bg-surface-raised text-code-fn border-hairline rounded border px-1.5 py-0.5 font-mono text-[0.9em]"
                {...props}
              >
                {children}
              </code>
            )
          },

          // Blockquotes — detect [!NOTE] / [!WARNING] callout syntax
          blockquote({ children }) {
            // Extract the first text node to detect the variant prefix
            const textContent = extractText(children)
            const variant = detectCalloutVariant(textContent)
            if (variant) {
              return <Callout variant={variant}>{stripLeadingMarker(children)}</Callout>
            }
            return (
              <blockquote className="border-brand-500/40 text-fg-subtle my-4 border-l-2 pl-4 italic">
                {children}
              </blockquote>
            )
          },

          // Tables
          table({ children }) {
            return (
              <div className="border-hairline my-5 overflow-x-auto rounded-md border">
                <table className="text-caption min-w-full border-collapse">
                  {children}
                </table>
              </div>
            )
          },
          th({ children }) {
            return (
              <th className="border-hairline bg-surface-raised text-fg sticky top-0 border-b px-3 py-2 text-left font-semibold">
                {children}
              </th>
            )
          },
          td({ children }) {
            return (
              <td className="border-hairline text-fg-muted border-t px-3 py-2">
                {children}
              </td>
            )
          },

          // Typography
          h1({ children }) {
            return <h1 className="text-title text-fg mt-8 mb-3">{children}</h1>
          },
          h2({ children }) {
            return <h2 className="text-headline text-fg mt-7 mb-2">{children}</h2>
          },
          h3({ children }) {
            return <h3 className="text-body-lg text-fg mt-5 mb-1.5 font-semibold">{children}</h3>
          },
          p({ children }) {
            return <p className="text-fg-muted mb-4">{children}</p>
          },
          ul({ children }) {
            return <ul className="text-fg-muted mb-4 list-disc space-y-1.5 pl-5">{children}</ul>
          },
          ol({ children }) {
            return <ol className="text-fg-muted mb-4 list-decimal space-y-1.5 pl-5">{children}</ol>
          },
          li({ children }) {
            return <li className="text-fg-muted">{children}</li>
          },
          strong({ children }) {
            return <strong className="text-fg font-semibold">{children}</strong>
          },
          hr() {
            return <hr className="border-hairline my-6" />
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

// Recursively pull text from React children (used for callout detection).
function extractText(node: React.ReactNode): string {
  if (typeof node === 'string') return node
  if (typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(extractText).join('')
  if (node && typeof node === 'object' && 'props' in (node as object)) {
    const el = node as React.ReactElement
    return extractText(el.props.children)
  }
  return ''
}
