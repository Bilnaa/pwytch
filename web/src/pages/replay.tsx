import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'

import { Avatar } from '@/components/avatar'
import { DownloadButton } from '@/components/download-button'
import { HlsPlayer } from '@/components/hls-player'
import { Badge } from '@/components/ui/badge'
import { ApiError, errorMessage } from '@/lib/api'
import { formatDate, formatDuration } from '@/lib/format'
import { getReplay, playbackUrl, type Replay } from '@/lib/replays'
import { NotFoundPage } from '@/pages/not-found'

interface Lookup {
  // which replay this answer is for, so a late answer for /replays/1 never shows on /replays/2
  id: string
  replay: Replay | null
  notFound: boolean
  error: string
}

// Replay page: the whole live, with a progress bar, and its mp4 to download
// /replays/abc or /replays/0: not a replay id, no need to ask main
function readStreamId(id: string): number | null {
  const streamId = Number(id)
  return Number.isInteger(streamId) && streamId >= 1 ? streamId : null
}

export function ReplayPage() {
  const { id = '' } = useParams()
  const streamId = readStreamId(id)
  const [lookup, setLookup] = useState<Lookup | null>(null)

  useEffect(() => {
    if (streamId === null) {
      return
    }
    let cancelled = false
    getReplay(streamId)
      .then((replay) => {
        if (!cancelled) {
          setLookup({ id, replay, notFound: false, error: '' })
        }
      })
      .catch((err) => {
        if (cancelled) {
          return
        }
        // 422 on an id out of range: same as an unknown replay for the viewer
        const notFound = err instanceof ApiError && (err.status === 404 || err.status === 422)
        setLookup({ id, replay: null, notFound, error: notFound ? '' : errorMessage(err) })
      })
    return () => {
      cancelled = true
    }
  }, [id, streamId])

  if (streamId === null) {
    return <NotFoundPage />
  }
  if (!lookup || lookup.id !== id) {
    return null
  }
  if (lookup.notFound) {
    return <NotFoundPage />
  }
  if (lookup.error || !lookup.replay) {
    return <p className="text-sm text-destructive">{lookup.error}</p>
  }
  const replay = lookup.replay
  const streamerName = replay.streamer_name

  return (
    <div className="space-y-4">
      <HlsPlayer src={playbackUrl(replay)} streamType="on-demand" />

      <div className="flex items-start gap-3">
        <Avatar username={streamerName ?? '?'} />
        <div className="min-w-0 flex-1">
          {streamerName ? (
            <Link to={`/${streamerName}`} className="font-semibold text-primary hover:underline">
              {streamerName}
            </Link>
          ) : (
            <p className="font-semibold text-muted-foreground">Unknown streamer</p>
          )}
          <h1 className="truncate text-lg font-semibold">{replay.title ?? 'Untitled'}</h1>
          <p className="text-sm text-muted-foreground">
            {[replay.game, formatDate(replay.ended_at), formatDuration(replay.duration_s)]
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
        <Badge variant="secondary">REPLAY</Badge>
        {/* key: another replay gets a new button, without the state or the polling of this one */}
        <DownloadButton
          key={replay.stream_id}
          streamId={replay.stream_id}
          status={replay.mp4_status}
        />
      </div>
    </div>
  )
}
