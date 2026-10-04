import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'

import { HlsPlayer } from '@/components/hls-player'
import { Badge } from '@/components/ui/badge'
import { ApiError, errorMessage } from '@/lib/api'
import { getStream, playlistUrl, type Stream } from '@/lib/streams'

export function LivePage() {
  const { streamId } = useParams()
  const id = Number(streamId)
  const [stream, setStream] = useState<Stream | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getStream(id)
      .then(setStream)
      .catch((err) => {
        // 422 = the id in the URL is not a number
        if (err instanceof ApiError && (err.status === 404 || err.status === 422)) {
          setError('Live not found')
        } else {
          setError(errorMessage(err))
        }
      })
  }, [id])

  if (error) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">{error}</h1>
        <Link to="/" className="text-sm text-primary hover:underline">
          Back to the lives
        </Link>
      </div>
    )
  }
  if (!stream) {
    return null
  }

  // created = the streamer clicked Go live but nothing arrived yet, the player waits for it
  const isLive = stream.status === 'live' || stream.status === 'created'

  return (
    <div className="space-y-4">
      {isLive ? (
        <HlsPlayer src={playlistUrl(stream.id)} />
      ) : (
        <div className="flex aspect-video items-center justify-center rounded-lg bg-black text-white/70">
          This live is over
        </div>
      )}

      <div className="flex items-start gap-3">
        <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary text-lg font-bold text-primary-foreground uppercase">
          {stream.streamer.username[0]}
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-primary">{stream.streamer.username}</p>
          <h1 className="truncate text-lg font-semibold">{stream.title}</h1>
          <p className="text-sm text-muted-foreground">{stream.game}</p>
        </div>
        {stream.status === 'live' && <Badge className="bg-red-600 text-white">LIVE</Badge>}
      </div>
    </div>
  )
}
