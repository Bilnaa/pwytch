import { useEffect, useState } from 'react'

export function useWebcam() {
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let media: MediaStream | null = null
    // StrictMode mounts twice in dev, don't keep the stream of the first mount
    let cancelled = false

    navigator.mediaDevices
      .getUserMedia({ video: true, audio: true })
      .then((result) => {
        if (cancelled) {
          result.getTracks().forEach((track) => track.stop())
          return
        }
        media = result
        setStream(result)
      })
      .catch((err: DOMException) => {
        if (err.name === 'NotAllowedError') {
          setError('Camera access was denied. Allow it in the browser settings and reload the page.')
        } else if (err.name === 'NotFoundError') {
          setError('No camera or microphone found.')
        } else {
          setError(`Cannot open the camera (${err.name}).`)
        }
      })

    return () => {
      cancelled = true
      // turns the camera light off when leaving the page
      media?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  return { stream, error }
}
