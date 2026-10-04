import { useEffect, useState } from 'react'
import { useParams } from 'react-router'

import { Avatar } from '@/components/avatar'
import { HlsPlayer } from '@/components/hls-player'
import { Badge } from '@/components/ui/badge'
import { errorMessage } from '@/lib/api'
import { findLive, playlistUrl, type Stream } from '@/lib/streams'

const REFRESH_MS = 15000

interface Lookup {
  // the channel this answer is for: after /a -> /b, an answer for /a is not shown
  username: string
  stream: Stream | null
  error: string
}

// /:username, like twitch.tv/<name>: the live of this streamer if there is one.
// Checked again every 15 s, so the page goes offline when the live ends and
// comes back when the streamer starts a new one
export function ChannelPage() {
  const { username = '' } = useParams()
  const [lookup, setLookup] = useState<Lookup | null>(null)
  // bumped when the video reaches its end, to check right away instead of in 15 s
  const [endedCount, setEndedCount] = useState(0)

  useEffect(() => {
    let cancelled = false

    function load() {
      findLive(username)
        .then((stream) => {
          if (!cancelled) {
            setLookup({ username, stream, error: '' })
          }
        })
        .catch((err) => {
          if (cancelled) {
            return
          }
          setLookup((old) => {
            // a failed refresh keeps what is on screen, only the first load shows the error
            if (old && old.username === username) {
              return old
            }
            return { username, stream: null, error: errorMessage(err) }
          })
        })
    }

    load()
    const timer = window.setInterval(load, REFRESH_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [username, endedCount])

  if (!lookup || lookup.username !== username) {
    return null
  }
  if (lookup.error) {
    return <p className="text-sm text-destructive">{lookup.error}</p>
  }
  const stream = lookup.stream

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
      <HlsPlayer src={playlistUrl(stream.id)} onEnded={() => setEndedCount((n) => n + 1)} />

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
