import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Radio, Square } from 'lucide-react'

import { FormField } from '@/components/form-field'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useBroadcast, type BroadcastStatus } from '@/hooks/use-broadcast'
import { useWebcam } from '@/hooks/use-webcam'
import { errorMessage } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { createStream, findMyOpenStream, type Stream } from '@/lib/streams'

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
  const { user } = useAuth()
  const webcam = useWebcam()
  const broadcast = useBroadcast(webcam.stream)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [title, setTitle] = useState('')
  const [game, setGame] = useState('')
  const [formError, setFormError] = useState('')
  // session still open on the server, Go live resumes it instead of creating one
  const [openStream, setOpenStream] = useState<Stream | null>(null)
  // after Stop, main may not have ended the session yet when the socket closes:
  // looking it up then would offer to resume a live that is over
  const stoppedRef = useRef(false)

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.srcObject = webcam.stream
    }
  }, [webcam.stream])

  // After a closed tab or a lost connection, stream keeps the live ~30 s for the
  // streamer to come back. Checked again each time we're not broadcasting anymore
  useEffect(() => {
    if (!user || broadcast.status === 'connecting' || broadcast.status === 'live') {
      return
    }
    if (stoppedRef.current) {
      stoppedRef.current = false
      return
    }
    findMyOpenStream(user.id)
      .then((stream) => {
        setOpenStream(stream)
        if (stream) {
          setTitle(stream.title)
          setGame(stream.game)
        }
      })
      .catch(() => setOpenStream(null))
  }, [user, broadcast.status])

  function handleStop() {
    stoppedRef.current = true
    setOpenStream(null)
    broadcast.stop()
  }

  async function handleGoLive(event: FormEvent) {
    event.preventDefault()
    setFormError('')
    if (openStream) {
      broadcast.start(openStream.id)
      return
    }
    try {
      const stream = await createStream(title, game)
      broadcast.start(stream.id)
    } catch (err) {
      setFormError(errorMessage(err))
    }
  }

  const busy = broadcast.status === 'connecting' || broadcast.status === 'live'
  // stream keeps the title and game of the first connection, no point editing them
  const locked = busy || openStream !== null

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
              disabled={locked}
            />
            <FormField
              id="game"
              label="Game"
              value={game}
              onChange={(e) => setGame(e.target.value)}
              required
              maxLength={50}
              disabled={locked}
            />
            {openStream && !busy && (
              <p className="text-sm text-muted-foreground">
                Your live is still open, you can pick it up where you left it.
              </p>
            )}
            {formError && <p className="text-sm text-destructive">{formError}</p>}
            {broadcast.error && <p className="text-sm text-destructive">{broadcast.error}</p>}

            {busy ? (
              <Button type="button" variant="destructive" className="w-full" onClick={handleStop}>
                <Square />
                Stop
              </Button>
            ) : (
              <Button type="submit" className="w-full" disabled={!webcam.stream}>
                <Radio />
                {openStream ? 'Resume live' : 'Go live'}
              </Button>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
