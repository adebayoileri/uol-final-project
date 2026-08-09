import { useEffect, useRef } from 'react'
import Prism from 'prismjs'
import 'prismjs/components/prism-python'
import 'prismjs/components/prism-javascript'
import 'prismjs/components/prism-typescript'
import 'prismjs/components/prism-bash'
import 'prismjs/components/prism-json'
import 'prismjs/components/prism-sql'

interface Props {
  code: string
  language?: string
}

function CodeBlock({ code, language = 'python' }: Props) {
  const ref = useRef<HTMLElement>(null)

  useEffect(() => {
    // Lesson content is LLM-generated, so the fence language is arbitrary.
    if (ref.current && Prism.languages[language]) Prism.highlightElement(ref.current)
  }, [code, language])

  return (
    <pre className="overflow-x-auto rounded-md border border-hairline bg-canvas-elevated p-4 leading-relaxed">
      <code ref={ref} className={`language-${language}`}>
        {code}
      </code>
    </pre>
  )
}

export default CodeBlock
