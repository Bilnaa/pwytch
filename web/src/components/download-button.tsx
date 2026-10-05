import { useEffect, useRef, useState } from 'react'
import { Download, LoaderCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { downloadUrl, getReplay, requestDownload, type Mp4Status } from '@/lib/replays'

type ButtonState = 'idle' | 'preparing' | 'failed'

// The browser saves the file itself (Content-Disposition: attachment), the page stays open
function saveFile(streamId: number) {
  const link = document.createElement('a')
  link.href = downloadUrl(streamId)
  link.download = ''
  link.click()
}

// "Download .mp4": the mp4 is only made on the first request. While replay converts,
// the button shows "Preparing..." and reads the replay again until the file is ready
export function DownloadButton({ streamId, status }: { streamId: number; status: Mp4Status }) {
  const [state, setState] = useState<ButtonState>(status === 'failed' ? 'failed' : 'idle')
  const [message, setMessage] = useState('')
  // last status seen, to know if the next request must restart a failed conversion
  const statusRef = useRef<Mp4Status>(status)
  const timerRef = useRef<number | undefined>(undefined)

  // leaving the page stops the polling
  useEffect(() => () => window.clearTimeout(timerRef.current), [])

  function fail(text: string) {
    statusRef.current = 'failed'
    setMessage(text)
    setState('failed')
  }

  function finish() {
    statusRef.current = 'ready'
    setState('idle')
    saveFile(streamId)
  }

  function waitForFile(delayMs: number) {
    setState('preparing')
    timerRef.current = window.setTimeout(async () => {
      try {
        const replay = await getReplay(streamId)
        if (replay.mp4_status === 'ready') {
          finish()
        } else if (replay.mp4_status === 'failed') {
          fail('Conversion failed')
        } else {
          waitForFile(delayMs)
        }
      } catch {
        fail('Cannot reach the server')
      }
    }, delayMs)
  }

  async function onClick() {
    if (statusRef.current === 'ready') {
      saveFile(streamId)
      return
    }
    setMessage('')
    setState('preparing')
    try {
      let answer = await requestDownload(streamId)
      // after a failure, replay answers 500 once and resets the conversion: ask again
      if (answer.state === 'failed' && statusRef.current === 'failed') {
        answer = await requestDownload(streamId)
      }
      if (answer.state === 'ready') {
        finish()
      } else if (answer.state === 'pending') {
        statusRef.current = 'processing'
        waitForFile(answer.retryAfterMs)
      } else {
        fail('Conversion failed')
      }
    } catch {
      fail('Cannot reach the server')
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button onClick={onClick} disabled={state === 'preparing'} variant="outline">
        {state === 'preparing' ? <LoaderCircle className="animate-spin" /> : <Download />}
        {state === 'preparing' && 'Preparing...'}
        {state === 'idle' && 'Download .mp4'}
        {state === 'failed' && 'Try again'}
      </Button>
      {state === 'failed' && (
        <p className="text-xs text-destructive">{message || 'Conversion failed'}</p>
      )}
    </div>
  )
}
