import { useEffect, useState } from 'react'
import { useParams } from 'react-router'

import { Avatar } from '@/components/avatar'
import { FollowButton } from '@/components/follow-button'
import { Chat } from '@/components/chat'
import { HlsPlayer } from '@/components/hls-player'
import { Badge } from '@/components/ui/badge'
import { usePlayerEvents } from '@/hooks/use-player-events'
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

// player of a live, its play / pause / stop go to the stats
function LivePlayer({ streamId, onEnded }: { streamId: number; onEnded: () => void }) {
  const events = usePlayerEvents(streamId)

  function handleEnded() {
    events.onEnded()
    onEnded()
  }

  return (
    <HlsPlayer
      src={playlistUrl(streamId)}
      onPlay={events.onPlay}
      onPause={events.onPause}
      onEnded={handleEnded}
    />
  )
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
      <div className="space-y-4 px-4 py-6">
        <div className="flex aspect-video max-h-[calc(100svh-12rem)] w-full items-center justify-center rounded-lg bg-black text-white/70">
          {user.display_name} is offline
        </div>
        <div className="flex items-center gap-3">
          <Avatar username={user.display_name} />
          <p className="flex-1 font-semibold">{user.display_name}</p>
          <FollowButton key={user.id} streamerId={user.id} username={user.username} />
        </div>
      </div>
    )
  }

  // on a wide screen the chat is a column glued to the right edge, as tall as the window
  // (like the followed channels on the left). On a phone it is under the player
  return (
    <div className="lg:flex">
      <div className="min-w-0 flex-1 space-y-4 px-4 py-6">
        <LivePlayer streamId={stream.id} onEnded={() => setEndedCount((n) => n + 1)} />


        <div className="flex items-start gap-3">
          <Avatar username={user.display_name} />
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-primary">{user.display_name}</p>
            <h1 className="truncate text-lg font-semibold">{stream.title}</h1>
            <p className="text-sm text-muted-foreground">{stream.game}</p>
          </div>
          <FollowButton key={user.id} streamerId={user.id} username={user.username} />
          <Badge className="bg-red-600 text-white">LIVE</Badge>
        </div>
      </div>

      {/* key: a new live of the same channel starts with an empty chat */}
      <Chat
        key={stream.id}
        streamId={stream.id}
        className="mx-4 mb-6 lg:sticky lg:top-12 lg:m-0 lg:h-[calc(100svh-3rem)] lg:w-80 lg:shrink-0 lg:rounded-none lg:border-y-0 lg:border-r-0"
      />
    </div>
  )
}
