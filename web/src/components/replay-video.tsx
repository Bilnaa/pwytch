import { useEffect, useState } from 'react'
import { LoaderCircle } from 'lucide-react'

import { HlsPlayer } from '@/components/hls-player'
import { DEFAULT_RETRY_MS, getReplay, playbackUrl, type Mp4Status, type Replay } from '@/lib/replays'

// A replay only plays its mp4, never the HLS of the live: until replay has converted it,
// the page shows that the video is being prepared and reads the replay again
export function ReplayVideo({ replay }: { replay: Replay }) {
  const [status, setStatus] = useState<Mp4Status>(replay.mp4_status)
  // bumped after a failed read, so the same status still schedules the next one
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (status === 'ready' || status === 'failed') {
      return
    }
    let cancelled = false
    const timer = window.setTimeout(async () => {
      try {
        const fresh = await getReplay(replay.stream_id)
        if (!cancelled) {
          setStatus(fresh.mp4_status)
        }
      } catch {
        // main unreachable for a moment: try again later
        if (!cancelled) {
          setAttempt((count) => count + 1)
        }
      }
    }, DEFAULT_RETRY_MS)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [status, attempt, replay.stream_id])

  if (status === 'ready') {
    return <HlsPlayer src={playbackUrl(replay)} type="video/mp4" streamType="on-demand" />
  }
  return (
    <div className="flex aspect-video max-h-[calc(100svh-12rem)] w-full flex-col items-center justify-center gap-2 rounded-lg bg-black text-sm text-muted-foreground">
      {status === 'failed' ? (
        <p>This replay could not be prepared</p>
      ) : (
        <>
          <LoaderCircle className="animate-spin" />
          <p>Preparing the replay...</p>
        </>
      )}
    </div>
  )
}
