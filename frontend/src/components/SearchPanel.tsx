import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { searchContent, type SearchResultItem } from '../api'

interface Props {
  courseId?: string
}

function SearchPanel({ courseId }: Props) {
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
    <div className="mt-4">
      <div className="relative">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search lessons and questions…"
          className="block w-full rounded-lg border border-[#2a2a3a] bg-[#111118] px-4 py-2 text-sm text-white placeholder-gray-500 focus:border-violet-500 focus:outline-none"
        />
        {loading && (
          <span className="absolute right-3 top-2 text-xs text-gray-500">Searching…</span>
        )}
      </div>

      {searched && results.length === 0 && !loading && (
        <p className="mt-2 text-sm text-gray-500">No results.</p>
      )}

      {results.length > 0 && (
        <ul className="mt-2 space-y-1">
          {results.map((r) => (
            <li key={r.content_id}>
              <Link
                to={`/courses/${r.course_id}`}
                className="flex items-start gap-3 rounded-lg border border-[#2a2a3a] bg-[#111118] px-4 py-2.5 text-sm hover:bg-[#1a1a24]"
              >
                <span
                  className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                    r.content_type === 'lesson'
                      ? 'bg-blue-900/50 text-blue-300'
                      : 'bg-violet-900/50 text-violet-300'
                  }`}
                >
                  {r.content_type === 'lesson' ? 'Lesson' : 'Question'}
                </span>
                <span className="text-gray-300">{r.content_text}</span>
                <span className="ml-auto shrink-0 text-xs text-gray-600">
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
