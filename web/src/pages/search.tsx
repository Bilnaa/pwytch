import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { Avatar } from '@/components/avatar'
import { Badge } from '@/components/ui/badge'
import { errorMessage } from '@/lib/api'
import { MIN_QUERY_LENGTH, search, type MessageResult, type StreamerResult } from '@/lib/search'

interface Results {
  // which query this answer is for, a late answer for "ab" must not replace "abc"
  query: string
  streamers: StreamerResult[]
  messages: MessageResult[]
  error: string
}

function StreamerRow({ streamer }: { streamer: StreamerResult }) {
  return (
    <Link to={`/${streamer.streamer_name}`} className="group flex items-center gap-3 rounded-lg p-2 hover:bg-muted">
      <Avatar username={streamer.streamer_name} className="size-10 text-base" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold group-hover:text-primary">{streamer.streamer_name}</p>
        {streamer.last_title && (
          <p className="truncate text-sm text-muted-foreground">
            {streamer.last_title}
            {streamer.last_game && ` · ${streamer.last_game}`}
          </p>
        )}
      </div>
      {streamer.is_live && <Badge className="bg-red-600 text-white">LIVE</Badge>}
    </Link>
  )
}

// a message only knows the id of its live, /videos/:id finds the channel on click
function MessageRow({ message }: { message: MessageResult }) {
  return (
    <Link to={`/videos/${message.stream_id}`} className="group block rounded-lg p-2 hover:bg-muted">
      <p className="text-sm">
        <span className="font-semibold text-primary">{message.author_name}</span>: {message.content}
      </p>
      <p className="text-xs text-muted-foreground group-hover:text-primary">
        {new Date(message.sent_at).toLocaleString()}
      </p>
    </Link>
  )
}

// /search?q=, filled by the search bar of the header. One call to main for both sections
export function SearchPage() {
  const [params] = useSearchParams()
  const query = (params.get('q') ?? '').trim()
  const [results, setResults] = useState<Results | null>(null)

  useEffect(() => {
    if (query.length < MIN_QUERY_LENGTH) {
      return
    }
    let cancelled = false
    search(query)
      .then(({ streamers, messages }) => {
        if (!cancelled) {
          setResults({ query, streamers, messages, error: '' })
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setResults({ query, streamers: [], messages: [], error: errorMessage(err) })
        }
      })
    return () => {
      cancelled = true
    }
  }, [query])

  if (query.length < MIN_QUERY_LENGTH) {
    return <p className="text-muted-foreground">Type at least {MIN_QUERY_LENGTH} characters to search.</p>
  }
  if (!results || results.query !== query) {
    return null
  }
  if (results.error) {
    return <p className="text-sm text-destructive">Search failed: {results.error}</p>
  }

  return (
    <div className="space-y-6">
      {results.streamers.length === 0 && results.messages.length === 0 && (
        <p className="text-muted-foreground">No results for "{query}".</p>
      )}

      {results.streamers.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Streamers</h2>
          {results.streamers.map((streamer) => (
            <StreamerRow key={streamer.streamer_id} streamer={streamer} />
          ))}
        </section>
      )}

      {results.messages.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Messages</h2>
          {results.messages.map((message) => (
            <MessageRow key={message.message_id} message={message} />
          ))}
        </section>
      )}
    </div>
  )
}
