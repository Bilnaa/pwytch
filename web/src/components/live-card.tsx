import { Link } from 'react-router'

import { Avatar } from '@/components/avatar'
import { Badge } from '@/components/ui/badge'
import { formatUptime } from '@/lib/format'
import type { Stream } from '@/lib/streams'

export function LiveCard({ stream, now }: { stream: Stream; now: number }) {
  const username = stream.streamer.username

  return (
    <Link to={`/${username}`} className="group space-y-2">
      {/* no thumbnails in the API yet, a gradient in the python colors instead */}
      <div className="relative aspect-video overflow-hidden rounded-lg bg-gradient-to-br from-primary to-secondary transition-transform group-hover:-translate-y-1 group-hover:shadow-[-6px_6px_0_var(--color-primary)]">
        <span className="absolute inset-0 flex items-center justify-center text-4xl font-bold text-white/80 uppercase">
          {username[0]}
        </span>
        <Badge className="absolute top-2 left-2 bg-red-600 text-white">LIVE</Badge>
        {stream.started_at && (
          <span className="absolute bottom-2 left-2 rounded bg-black/70 px-1.5 text-xs text-white">
            {formatUptime(stream.started_at, now)}
          </span>
        )}
      </div>
      <div className="flex gap-2">
        <Avatar username={username} className="size-8 text-sm" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold group-hover:text-primary">{stream.title}</p>
          <p className="truncate text-sm text-muted-foreground">{username}</p>
          <p className="truncate text-sm text-muted-foreground">{stream.game}</p>
        </div>
      </div>
    </Link>
  )
}
