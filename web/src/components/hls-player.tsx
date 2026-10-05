import { useEffect, useRef } from 'react'
import '@vidstack/react/player/styles/default/theme.css'
import '@vidstack/react/player/styles/default/layouts/video.css'
import {
  isHLSProvider,
  MediaPlayer,
  MediaProvider,
  type HLSErrorEvent,
  type HLSProvider,
  type MediaPlayerInstance,
  type MediaProviderAdapter,
} from '@vidstack/react'
import { DefaultVideoLayout, defaultLayoutIcons } from '@vidstack/react/player/layouts/default'
// light build: no DRM or subtitles, we don't need them
import Hls from 'hls.js/light'

const RETRY_MS = 3000

interface HlsPlayerProps {
  src: string
  // 'on-demand' for a replay: full progress bar, and a missing playlist is not retried
  streamType?: 'live' | 'on-demand'
  onPlay?: () => void
  onPause?: () => void
  // the playlist is over (#EXT-X-ENDLIST reached), the live has ended
  onEnded?: () => void
}

export function HlsPlayer({
  src,
  streamType = 'live',
  onPlay,
  onPause,
  onEnded,
}: HlsPlayerProps) {
  const playerRef = useRef<MediaPlayerInstance>(null)
  const hlsRef = useRef<HLSProvider | null>(null)
  const retryRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    return () => window.clearTimeout(retryRef.current)
  }, [src])

  function onProviderChange(provider: MediaProviderAdapter | null) {
    if (!isHLSProvider(provider)) {
      return
    }
    // without this vidstack downloads hls.js from a CDN
    provider.library = Hls
    provider.config = { liveSyncDurationCount: 3 }
    hlsRef.current = provider
  }

  // vidstack already recovers media errors, network ones are left to us
  function onHlsError(error: HLSErrorEvent['detail']) {
    if (!error.fatal || error.type !== Hls.ErrorTypes.NETWORK_ERROR || streamType !== 'live') {
      return
    }
    // the playlist is a 404 for the first seconds of a live, so we try again
    window.clearTimeout(retryRef.current)
    retryRef.current = window.setTimeout(() => hlsRef.current?.instance?.loadSource(src), RETRY_MS)
  }

  // browsers block autoplay with sound, the viewer can unmute with the controls
  function onAutoPlayFail() {
    const player = playerRef.current
    if (!player) {
      return
    }
    player.muted = true
    player.play().catch(() => {})
  }

  // height capped like on twitch, so the title stays visible under the player
  return (
    <MediaPlayer
      ref={playerRef}
      src={{ src, type: 'application/x-mpegurl' }}
      streamType={streamType}
      autoPlay
      playsInline
      className="aspect-video max-h-[calc(100svh-12rem)] w-full overflow-hidden rounded-lg bg-black"
      onProviderChange={onProviderChange}
      onHlsError={onHlsError}
      onAutoPlayFail={onAutoPlayFail}
      onPlay={onPlay}
      onPause={onPause}
      onEnded={onEnded}
    >
      <MediaProvider />
      <DefaultVideoLayout icons={defaultLayoutIcons} />
    </MediaPlayer>
  )
}
