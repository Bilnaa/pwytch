import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Radio, Square } from 'lucide-react'

import { FormField } from '@/components/form-field'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useBroadcast, type BroadcastStatus } from '@/hooks/use-broadcast'
import { useWebcam } from '@/hooks/use-webcam'
import { ApiError, errorMessage } from '@/lib/api'
import { createStream } from '@/lib/streams'

function StatusBadge({ status }: { status: BroadcastStatus }) {
  if (status === 'live') {
    // same red as the LIVE badge on twitch
    return <Badge className="bg-red-600 text-white">LIVE</Badge>
  }
  if (status === 'connecting') {
    return <Badge variant="outline">Connecting...</Badge>
  }
  if (status === 'error') {
    return <Badge variant="destructive">Error</Badge>
  }
  return <Badge variant="secondary">Offline</Badge>
}

export function GoLivePage() {
  const webcam = useWebcam()
  const broadcast = useBroadcast(webcam.stream)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [title, setTitle] = useState('')
  const [game, setGame] = useState('')
  const [formError, setFormError] = useState('')

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.srcObject = webcam.stream
    }
  }, [webcam.stream])

  async function handleGoLive(event: FormEvent) {
    event.preventDefault()
    setFormError('')
    try {
      // a new session each time, main refuses to reuse an ended one (4409)
      const stream = await createStream(title, game)
      broadcast.start(stream.id)
    } catch (err) {
      // after Stop, stream keeps the session ~30 s in case the streamer comes back
      if (err instanceof ApiError && err.status === 409) {
        setFormError('Your last live is still closing, try again in a few seconds.')
      } else {
        setFormError(errorMessage(err))
      }
    }
  }

  const busy = broadcast.status === 'connecting' || broadcast.status === 'live'

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[1fr_320px]">
      <div className="relative aspect-video overflow-hidden rounded-lg bg-black">
        {/* muted, otherwise the streamer hears themselves */}
        <video ref={videoRef} autoPlay muted playsInline className="size-full object-cover" />
        {webcam.error && (
          <p className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-white">
            {webcam.error}
          </p>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Stream info</CardTitle>
          <CardAction>
            <StatusBadge status={broadcast.status} />
          </CardAction>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleGoLive} className="space-y-4">
            <FormField
              id="title"
              label="Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={100}
              disabled={busy}
            />
            <FormField
              id="game"
              label="Game"
              value={game}
              onChange={(e) => setGame(e.target.value)}
              required
              maxLength={50}
              disabled={busy}
            />
            {formError && <p className="text-sm text-destructive">{formError}</p>}
            {broadcast.error && <p className="text-sm text-destructive">{broadcast.error}</p>}

            {busy ? (
              <Button type="button" variant="destructive" className="w-full" onClick={broadcast.stop}>
                <Square />
                Stop
              </Button>
            ) : (
              <Button type="submit" className="w-full" disabled={!webcam.stream}>
                <Radio />
                Go live
              </Button>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
