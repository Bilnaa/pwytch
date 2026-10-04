import { useEffect, useRef } from 'react'

import { sendPlayerEvent } from '@/lib/streams'

// play / pause / stop of the player for the stats. Stop = the live ended, or the
// viewer left while it was playing
export function usePlayerEvents(streamId: number) {
  // so leaving a paused video doesn't send a stop on top of the pause
  const playingRef = useRef(false)

  useEffect(() => {
    function stop() {
      if (!playingRef.current) {
        return
      }
      playingRef.current = false
      sendPlayerEvent(streamId, 'stop')
    }

    // closing the tab doesn't unmount anything, pagehide still fires
    window.addEventListener('pagehide', stop)
    return () => {
      window.removeEventListener('pagehide', stop)
      stop()
    }
  }, [streamId])

  function onPlay() {
    playingRef.current = true
    sendPlayerEvent(streamId, 'play')
  }

  function onPause() {
    if (!playingRef.current) {
      return
    }
    playingRef.current = false
    sendPlayerEvent(streamId, 'pause')
  }

  function onEnded() {
    playingRef.current = false
    sendPlayerEvent(streamId, 'stop')
  }

  return { onPlay, onPause, onEnded }
}
