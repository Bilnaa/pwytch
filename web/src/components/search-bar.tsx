import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router'
import { Search } from 'lucide-react'

import { Input } from '@/components/ui/input'

const DEBOUNCE_MS = 300

// In the header like on twitch. Enter opens /search, and once there the results
// follow what is typed, so another page isn't left just by typing
export function SearchBar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [params] = useSearchParams()
  const onSearchPage = pathname === '/search'
  const query = onSearchPage ? (params.get('q') ?? '') : ''
  const [text, setText] = useState(query)
  const [shownQuery, setShownQuery] = useState(query)

  // back / forward on /search, or leaving it: the field shows the url again.
  // Done while rendering and not in an effect, see "storing information from
  // previous renders" in the react docs
  if (query !== shownQuery) {
    setShownQuery(query)
    if (text.trim() !== query) {
      setText(query)
    }
  }

  useEffect(() => {
    if (!onSearchPage || text.trim() === query) {
      return
    }
    const timer = window.setTimeout(() => {
      // replace: one history entry for the whole word, not one per letter
      navigate(`/search?q=${encodeURIComponent(text.trim())}`, { replace: true })
    }, DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [text, query, onSearchPage, navigate])

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (text.trim()) {
      navigate(`/search?q=${encodeURIComponent(text.trim())}`)
    }
  }

  return (
    <form onSubmit={handleSubmit} role="search" className="relative w-full max-w-sm">
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder="Search"
        aria-label="Search a streamer or a message"
        className="pl-8"
      />
    </form>
  )
}
