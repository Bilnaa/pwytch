import { useEffect, useState } from 'react'

import { LiveCard } from '@/components/live-card'
import { errorMessage } from '@/lib/api'
import { listLives, type Stream } from '@/lib/streams'

const REFRESH_MS = 15000

export function HomePage() {
  const [lives, setLives] = useState<Stream[] | null>(null)
  const [error, setError] = useState('')
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    function load() {
      listLives()
        .then((result) => {
          setLives(result)
          setError('')
          setNow(Date.now())
        })
        // the old list stays on screen, only the message is added
        .catch((err) => setError(errorMessage(err)))
    }

    load()
    const timer = window.setInterval(load, REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Live channels (demo)</h1>

      {error && <p className="text-sm text-destructive">Cannot load the lives: {error}</p>}

      {lives && lives.length === 0 && (
        <p className="text-muted-foreground">Nobody is live right now. Be the first one!</p>
      )}

      {lives && lives.length > 0 && (
        <div className="grid gap-x-4 gap-y-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {lives.map((stream) => (
            <LiveCard key={stream.id} stream={stream} now={now} />
          ))}
        </div>
      )}
    </div>
  )
}
