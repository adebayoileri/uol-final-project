import { useEffect, useRef } from 'react'
import Prism from 'prismjs'
import 'prismjs/components/prism-python'

interface Props {
  code: string
  language?: string
}

function CodeBlock({ code, language = 'python' }: Props) {
  const ref = useRef<HTMLElement>(null)

  useEffect(() => {
    if (ref.current) Prism.highlightElement(ref.current)
  }, [code, language])

  return (
    <pre className="overflow-x-auto rounded-lg bg-[#0d0d14] p-4 text-sm leading-relaxed">
      <code ref={ref} className={`language-${language}`}>
        {code}
      </code>
    </pre>
  )
}

export default CodeBlock
