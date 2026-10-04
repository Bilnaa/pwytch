import { useEffect, useState } from 'react'
import { useParams } from 'react-router'

import { Avatar } from '@/components/avatar'
import { HlsPlayer } from '@/components/hls-player'
import { Badge } from '@/components/ui/badge'
import { errorMessage } from '@/lib/api'
import { findLive, playlistUrl, type Stream } from '@/lib/streams'

// /:username, like twitch.tv/<name>: the live of this streamer if there is one
export function ChannelPage() {
  const { username = '' } = useParams()
  const [stream, setStream] = useState<Stream | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    findLive(username)
      .then(setStream)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [username])

  if (loading) {
    return null
  }
  if (error) {
    return <p className="text-sm text-destructive">{error}</p>
  }

  // no way to tell an unknown user from an offline one with the current API
  if (!stream) {
    return (
      <div className="space-y-4">
        <div className="flex aspect-video max-h-[calc(100svh-12rem)] w-full items-center justify-center rounded-lg bg-black text-white/70">
          {username} is offline
        </div>
        <div className="flex items-center gap-3">
          <Avatar username={username} />
          <p className="font-semibold">{username}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <HlsPlayer src={playlistUrl(stream.id)} />

      <div className="flex items-start gap-3">
        <Avatar username={stream.streamer.username} />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-primary">{stream.streamer.username}</p>
          <h1 className="truncate text-lg font-semibold">{stream.title}</h1>
          <p className="text-sm text-muted-foreground">{stream.game}</p>
        </div>
        <Badge className="bg-red-600 text-white">LIVE</Badge>
      </div>
    </div>
  )
}
