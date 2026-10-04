import { useEffect, useRef, useState } from 'react'

import { getToken, wsUrl } from '@/lib/api'

export type BroadcastStatus = 'offline' | 'connecting' | 'live' | 'error'

// Stop: main and stream end the live right away. Any other close (tab closed,
// leaving the page) is a cut, the live waits ~30 s for the streamer to resume it
const LIVE_ENDED = 4000

// Close codes sent by main on the ingest WebSocket (see main/README.md)
const CLOSE_MESSAGES: Record<number, string> = {
  4401: 'Your session expired, log in again.',
  4403: 'This live belongs to another streamer.',
  4404: 'This live does not exist.',
  4409: 'This live is over, start a new one.',
  4423: 'You are already live from another tab.',
  1003: 'The browser sent invalid data.',
  1011: 'The stream service is unavailable, try again.',
  1013: 'Signal lost, the server did not receive any video.',
  // no close frame at all: main is down or the network dropped
  1006: 'Cannot reach the server.',
}

// Chrome and Firefox record WebM, the first supported type wins
const MIME_TYPES = ['video/webm;codecs=vp8,opus', 'video/webm;codecs=vp9,opus', 'video/webm']

function pickMimeType(): string | null {
  for (const type of MIME_TYPES) {
    if (MediaRecorder.isTypeSupported(type)) {
      return type
    }
  }
  return null
}

export function useBroadcast(media: MediaStream | null) {
  const [status, setStatus] = useState<BroadcastStatus>('offline')
  const [error, setError] = useState('')
  const socketRef = useRef<WebSocket | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)

  function stopRecorder() {
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop()
    }
    recorderRef.current = null
  }

  function start(streamId: number) {
    const mimeType = pickMimeType()
    if (!media || !mimeType) {
      setStatus('error')
      setError('This browser cannot record WebM video, use Chrome or Firefox.')
      return
    }

    setError('')
    setStatus('connecting')
    const socket = new WebSocket(wsUrl(`/streams/${streamId}/ingest?token=${getToken()}`))
    socketRef.current = socket

    // main only relays binary chunks, so the recorder waits for the socket
    socket.onopen = () => {
      const recorder = new MediaRecorder(media, { mimeType })
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
          socket.send(event.data)
        }
      }
      recorder.start(1000)
      recorderRef.current = recorder
      setStatus('live')
    }

    socket.onclose = (event) => {
      stopRecorder()
      socketRef.current = null
      // we closed it ourselves: Stop, or leaving the page
      if (event.code === LIVE_ENDED || event.code === 1000) {
        setStatus('offline')
        return
      }
      setStatus('error')
      setError(CLOSE_MESSAGES[event.code] ?? `Connection closed (${event.code} ${event.reason})`)
    }
  }

  function stop() {
    stopRecorder()
    socketRef.current?.close(LIVE_ENDED, 'Live ended')
  }

  // leaving the page is a cut, not an end: the live can be resumed from /go-live
  useEffect(() => {
    return () => {
      stopRecorder()
      socketRef.current?.close(1000)
    }
  }, [])

  return { status, error, start, stop }
}
