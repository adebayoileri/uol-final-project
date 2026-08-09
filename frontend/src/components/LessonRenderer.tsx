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

function stripCalloutPrefix(text: string): string {
  return text.replace(/^\[!(?:NOTE|WARNING)\]\s*/i, '').trim()
}

export default function LessonRenderer({ content }: LessonRendererProps) {
  return (
    <div className="prose-lesson text-sm text-gray-300 leading-relaxed">
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
                className="bg-[#1a1a24] text-violet-300 px-1 py-0.5 rounded text-xs font-mono"
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
              const cleaned = stripCalloutPrefix(textContent)
              return <Callout variant={variant}>{cleaned}</Callout>
            }
            return (
              <blockquote className="border-l-2 border-[#2a2a3a] pl-3 text-gray-400 italic my-3">
                {children}
              </blockquote>
            )
          },

          // Tables
          table({ children }) {
            return (
              <div className="overflow-x-auto my-4">
                <table className="min-w-full border-collapse text-xs">
                  {children}
                </table>
              </div>
            )
          },
          th({ children }) {
            return (
              <th className="border border-[#2a2a3a] bg-[#1a1a24] px-3 py-1.5 text-left text-gray-300 font-semibold">
                {children}
              </th>
            )
          },
          td({ children }) {
            return (
              <td className="border border-[#2a2a3a] px-3 py-1.5 text-gray-400">
                {children}
              </td>
            )
          },

          // Typography
          h1({ children }) {
            return <h1 className="text-base font-bold text-white mt-5 mb-2">{children}</h1>
          },
          h2({ children }) {
            return <h2 className="text-sm font-semibold text-white mt-4 mb-1.5">{children}</h2>
          },
          h3({ children }) {
            return <h3 className="text-sm font-medium text-gray-200 mt-3 mb-1">{children}</h3>
          },
          p({ children }) {
            return <p className="mb-3 text-gray-300">{children}</p>
          },
          ul({ children }) {
            return <ul className="list-disc pl-5 mb-3 space-y-1 text-gray-300">{children}</ul>
          },
          ol({ children }) {
            return <ol className="list-decimal pl-5 mb-3 space-y-1 text-gray-300">{children}</ol>
          },
          li({ children }) {
            return <li className="text-gray-300">{children}</li>
          },
          strong({ children }) {
            return <strong className="font-semibold text-white">{children}</strong>
          },
          hr() {
            return <hr className="border-[#2a2a3a] my-4" />
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
