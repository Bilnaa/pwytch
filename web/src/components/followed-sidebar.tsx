import { useEffect, useState } from 'react'
import { NavLink } from 'react-router'

import { Avatar } from '@/components/avatar'
import { useAuth } from '@/lib/auth'
import { FOLLOWS_CHANGED, listBookmarks } from '@/lib/bookmarks'
import { listLives, type Stream } from '@/lib/streams'
import { getUsers } from '@/lib/users'
import { cn } from '@/lib/utils'

const REFRESH_MS = 15000

interface Channel {
  id: number
  username: string
  // undefined when offline
  live?: Stream
}

// follows (bookmarks of type streamer) + their names + who is live: 3 calls, the
// last two at the same time
async function loadChannels(): Promise<Channel[]> {
  const follows = await listBookmarks(1, 100, 'streamer')
  if (follows.items.length === 0) {
    return []
  }
  const ids: number[] = []
  for (const follow of follows.items) {
    ids.push(follow.target_id)
  }
  const [users, lives] = await Promise.all([getUsers(ids), listLives()])

  const liveByStreamer = new Map<number, Stream>()
  for (const stream of lives) {
    liveByStreamer.set(stream.streamer.id, stream)
  }
  const channels: Channel[] = []
  for (const user of users) {
    channels.push({ id: user.id, username: user.username, live: liveByStreamer.get(user.id) })
  }
  // like on twitch: the lives first, then the others by name
  channels.sort((a, b) => {
    if (Boolean(a.live) !== Boolean(b.live)) {
      return a.live ? -1 : 1
    }
    return a.username.localeCompare(b.username)
  })
  return channels
}

function ChannelRow({ channel }: { channel: Channel }) {
  return (
    <NavLink
      to={`/${channel.username}`}
      className={({ isActive }) => cn('flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted', isActive && 'bg-muted')}
    >
      <Avatar username={channel.username} className={cn('size-8 text-sm', !channel.live && 'opacity-50 grayscale')} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{channel.username}</p>
        {channel.live && <p className="truncate text-xs text-muted-foreground">{channel.live.game}</p>}
      </div>
      {channel.live ? (
        <span className="flex items-center gap-1 text-xs">
          <span className="size-2 rounded-full bg-red-600" />
          Live
        </span>
      ) : (
        <span className="text-xs text-muted-foreground">Offline</span>
      )}
    </NavLink>
  )
}

// Left column with the followed channels, only for a logged in user and on a wide screen
export function FollowedSidebar() {
  const { user } = useAuth()
  const [channels, setChannels] = useState<Channel[] | null>(null)

  // another account logged in: don't show the follows of the previous one meanwhile
  const [owner, setOwner] = useState(user?.id)
  if (owner !== user?.id) {
    setOwner(user?.id)
    setChannels(null)
  }

  useEffect(() => {
    if (!user) {
      return
    }
    let cancelled = false

    function load() {
      loadChannels()
        .then((result) => {
          if (!cancelled) {
            setChannels(result)
          }
        })
        // a failed refresh keeps the old list, the next one will try again
        .catch(() => {})
    }

    load()
    const timer = window.setInterval(load, REFRESH_MS)
    window.addEventListener(FOLLOWS_CHANGED, load)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      window.removeEventListener(FOLLOWS_CHANGED, load)
    }
  }, [user])

  if (!user) {
    return null
  }

  return (
    <aside className="sticky top-12 hidden h-[calc(100svh-3rem)] w-60 shrink-0 overflow-y-auto border-r bg-card p-2 lg:block">
      <h2 className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase">Followed channels</h2>
      {channels && channels.length === 0 && (
        <p className="px-2 text-sm text-muted-foreground">Follow a channel to see it here.</p>
      )}
      {channels && channels.map((channel) => <ChannelRow key={channel.id} channel={channel} />)}
    </aside>
  )
}
