import { Link } from 'react-router'

import { Avatar } from '@/components/avatar'
import { formatDate, formatDuration } from '@/lib/format'
import type { Replay } from '@/lib/replays'

export function ReplayCard({ replay }: { replay: Replay }) {
  const streamerName = replay.streamer_name ?? 'Unknown streamer'

  return (
    <Link to={`/replays/${replay.stream_id}`} className="group space-y-2">
      {/* same gradient as the live cards, no thumbnails in the API yet */}
      <div className="relative aspect-video overflow-hidden rounded-lg bg-gradient-to-br from-primary to-secondary transition-transform group-hover:-translate-y-1 group-hover:shadow-[-6px_6px_0_var(--color-primary)]">
        <span className="absolute inset-0 flex items-center justify-center text-4xl font-bold text-white/80 uppercase">
          {streamerName[0]}
        </span>
        <span className="absolute bottom-2 left-2 rounded bg-black/70 px-1.5 text-xs text-white">
          {formatDuration(replay.duration_s)}
        </span>
      </div>
      <div className="flex gap-2">
        <Avatar username={streamerName} className="size-8 text-sm" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold group-hover:text-primary">
            {replay.title ?? 'Untitled'}
          </p>
          <p className="truncate text-sm text-muted-foreground">{streamerName}</p>
          <p className="truncate text-sm text-muted-foreground">
            {[replay.game, formatDate(replay.ended_at)].filter(Boolean).join(' · ')}
          </p>
        </div>
      </div>
    </Link>
  )
}
