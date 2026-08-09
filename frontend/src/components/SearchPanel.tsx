import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { searchContent, type SearchResultItem } from '../api'
import { Badge, Spinner } from './ui'
import { cn } from '../lib/cn'

interface Props {
  courseId?: string
  className?: string
}

function SearchPanel({ courseId, className }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([])
      setSearched(false)
      return
    }
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const data = await searchContent(query.trim(), courseId)
        setResults(data)
        setSearched(true)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query, courseId])

  return (
    <div className={cn('space-y-2', className)}>
      <div className="relative">
        <label htmlFor="content-search" className="sr-only">
          Search lessons and questions
        </label>
        <Search
          size={16}
          className="text-fg-faint pointer-events-none absolute top-1/2 left-3 -translate-y-1/2"
          aria-hidden="true"
        />
        <input
          id="content-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search lessons and questions…"
          className="border-border bg-surface-raised text-callout text-fg placeholder:text-fg-faint hover:border-border-strong focus:border-brand-500 block w-full rounded-md border py-2.5 pr-10 pl-9 transition-colors duration-[--duration-fast]"
        />
        {loading && (
          <span className="absolute top-1/2 right-3 -translate-y-1/2">
            <Spinner size="sm" className="text-fg-faint" />
          </span>
        )}
      </div>

      <p className="sr-only" aria-live="polite">
        {loading
          ? 'Searching'
          : searched
            ? `${results.length} result${results.length === 1 ? '' : 's'}`
            : ''}
      </p>

      {searched && results.length === 0 && !loading && (
        <p className="text-caption text-fg-subtle px-1">No matches.</p>
      )}

      {results.length > 0 && (
        <ul className="space-y-1.5">
          {results.map((r) => (
            <li key={r.content_id}>
              <Link
                to={
                  r.lesson_id
                    ? `/courses/${r.course_id}/lessons/${r.lesson_id}`
                    : `/courses/${r.course_id}`
                }
                className="border-border bg-surface hover:border-border-strong hover:bg-surface-raised flex items-start gap-2.5 rounded-md border px-3 py-2.5 transition-colors"
              >
                <Badge
                  tone={r.content_type === 'lesson' ? 'info' : 'brand'}
                  size="sm"
                  className="mt-0.5 shrink-0"
                >
                  {r.content_type === 'lesson' ? 'Lesson' : 'Question'}
                </Badge>
                <span className="text-caption text-fg-muted line-clamp-2 min-w-0 flex-1">
                  {r.content_text}
                </span>
                <span className="text-caption text-fg-faint shrink-0 tabular-nums">
                  {Math.round(r.score * 100)}%
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default SearchPanel
