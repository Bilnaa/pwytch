import { useEffect, useRef, useState } from 'react'
// light build: no DRM or subtitles, we don't need them
import Hls from 'hls.js/light'

const RETRY_MS = 3000

export function HlsPlayer({ src }: { src: string }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [waiting, setWaiting] = useState(true)

  useEffect(() => {
    const video = videoRef.current
    if (!video) {
      return
    }

    // Safari reads HLS by itself, hls.js is for the others
    if (!Hls.isSupported()) {
      video.src = src
      return
    }

    const hls = new Hls({ liveSyncDurationCount: 3 })
    let retry: number | undefined

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      // browsers block autoplay with sound, the viewer can unmute with the controls
      video.play().catch(() => {
        video.muted = true
        video.play()
      })
    })

    hls.on(Hls.Events.ERROR, (_event, data) => {
      if (!data.fatal) {
        return
      }
      if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
        hls.recoverMediaError()
        return
      }
      // the playlist is a 404 for the first seconds of a live, so we try again
      setWaiting(true)
      retry = window.setTimeout(() => hls.loadSource(src), RETRY_MS)
    })

    hls.loadSource(src)
    hls.attachMedia(video)

    return () => {
      window.clearTimeout(retry)
      hls.destroy()
    }
  }, [src])

  // height capped like on twitch, so the title stays visible under the player
  return (
    <div className="relative aspect-video max-h-[calc(100svh-12rem)] w-full overflow-hidden rounded-lg bg-black">
      <video
        ref={videoRef}
        controls
        playsInline
        className="size-full object-contain"
        onPlaying={() => setWaiting(false)}
      />
      {waiting && (
        <p className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-white/70">
          Waiting for the stream...
        </p>
      )}
    </div>
  )
}
