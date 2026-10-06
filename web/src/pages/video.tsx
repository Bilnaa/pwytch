import { useEffect, useState } from 'react'
import { Navigate, useParams } from 'react-router'

import { ApiError, errorMessage } from '@/lib/api'
import { getStream, type Stream } from '@/lib/streams'
import { NotFoundPage } from '@/pages/not-found'

interface Lookup {
  id: string
  stream: Stream | null
  error: string
}

// /videos/{id}, like twitch: a live known only by its id (a chat message in the
// search, the admin stats) is sent to its channel, or to its replay once it has ended
export function VideoPage() {
  const { id = '' } = useParams()
  const [lookup, setLookup] = useState<Lookup | null>(null)

  useEffect(() => {
    let cancelled = false
    getStream(Number(id))
      .then((stream) => {
        if (!cancelled) {
          setLookup({ id, stream, error: '' })
        }
      })
      .catch((err) => {
        if (cancelled) {
          return
        }
        // a 404, or a 422 for an id that isn't a number: no such video
        if (err instanceof ApiError && (err.status === 404 || err.status === 422)) {
          setLookup({ id, stream: null, error: '' })
        } else {
          setLookup({ id, stream: null, error: errorMessage(err) })
        }
      })
    return () => {
      cancelled = true
    }
  }, [id])

  if (!lookup || lookup.id !== id) {
    return null
  }
  if (lookup.error) {
    return <p className="text-sm text-destructive">{lookup.error}</p>
  }
  if (!lookup.stream) {
    return <NotFoundPage />
  }
  if (lookup.stream.status === 'ended') {
    return <Navigate to={`/replays/${lookup.stream.id}`} replace />
  }
  return <Navigate to={`/${lookup.stream.streamer.username}`} replace />
}
