import { useEffect, useState } from 'react'
import { useParams } from 'react-router'

import { Avatar } from '@/components/avatar'
import { HlsPlayer } from '@/components/hls-player'
import { Badge } from '@/components/ui/badge'
import { errorMessage } from '@/lib/api'
import { NotFoundPage } from '@/pages/not-found'
import { findLive, playlistUrl, type Stream } from '@/lib/streams'
import { getUser, type PublicUser } from '@/lib/users'

const REFRESH_MS = 15000

interface Lookup {
  // which channel this answer is for, so a late answer for /a never shows on /b
  username: string
  user: PublicUser | null
  stream: Stream | null
  error: string
}

// Channel page, like twitch.tv/<name>. Refreshed every 15 s to follow the live
export function ChannelPage() {
  const { username = '' } = useParams()
  const [lookup, setLookup] = useState<Lookup | null>(null)
  // bumped when the video reaches its end, to check right away instead of in 15 s
  const [endedCount, setEndedCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    let timer: number | undefined

    function load() {
      Promise.all([getUser(username), findLive(username)])
        .then(([user, stream]) => {
          if (cancelled) {
            return
          }
          setLookup({ username, user, stream, error: '' })
          // unknown account: it's a 404 page, nothing to follow
          if (!user) {
            window.clearInterval(timer)
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
            return { username, user: null, stream: null, error: errorMessage(err) }
          })
        })
    }

    load()
    timer = window.setInterval(load, REFRESH_MS)
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
  if (!lookup.user) {
    return <NotFoundPage />
  }
  const user = lookup.user
  const stream = lookup.stream

  if (!stream) {
    return (
      <div className="space-y-4">
        <div className="flex aspect-video max-h-[calc(100svh-12rem)] w-full items-center justify-center rounded-lg bg-black text-white/70">
          {user.display_name} is offline
        </div>
        <div className="flex items-center gap-3">
          <Avatar username={user.display_name} />
          <p className="font-semibold">{user.display_name}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <HlsPlayer src={playlistUrl(stream.id)} onEnded={() => setEndedCount((n) => n + 1)} />

      <div className="flex items-start gap-3">
        <Avatar username={user.display_name} />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-primary">{user.display_name}</p>
          <h1 className="truncate text-lg font-semibold">{stream.title}</h1>
          <p className="text-sm text-muted-foreground">{stream.game}</p>
        </div>
        <Badge className="bg-red-600 text-white">LIVE</Badge>
      </div>
    </div>
  )
}
