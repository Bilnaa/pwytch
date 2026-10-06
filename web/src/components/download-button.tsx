import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { Download, LoaderCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DEFAULT_RETRY_MS,
  downloadUrl,
  getReplay,
  requestDownload,
  type Mp4Status,
} from '@/lib/replays'

type ButtonState = 'idle' | 'preparing' | 'failed'

// The browser saves the file itself (Content-Disposition: attachment), the page stays open
function saveFile(streamId: number) {
  const link = document.createElement('a')
  link.href = downloadUrl(streamId)
  link.download = ''
  link.click()
}

function initialState(status: Mp4Status): ButtonState {
  if (status === 'failed') {
    return 'failed'
  }
  if (status === 'processing') {
    return 'preparing'
  }
  return 'idle'
}

// "Download .mp4": replay converts the mp4 when the live ends. While it converts,
// the button shows "Preparing..." and reads the replay again until the file is ready
export function DownloadButton({ streamId, status }: { streamId: number; status: Mp4Status }) {
  const [state, setState] = useState<ButtonState>(initialState(status))
  const [message, setMessage] = useState('')
  // last status seen, to know if the next request must restart a failed conversion
  const statusRef = useRef<Mp4Status>(status)
  const timerRef = useRef<number | undefined>(undefined)
  const mountedRef = useRef(true)

  // page opened during the conversion: wait for it, but only a click saves the file
  const waitIfProcessing = useEffectEvent(() => {
    if (status === 'processing') {
      waitForFile(DEFAULT_RETRY_MS, false)
    }
  })

  // leaving the page (or opening another replay) stops the polling
  useEffect(() => {
    mountedRef.current = true
    waitIfProcessing()
    return () => {
      mountedRef.current = false
      window.clearTimeout(timerRef.current)
    }
  }, [])

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

  function waitForFile(delayMs: number, saveWhenReady: boolean) {
    setState('preparing')
    timerRef.current = window.setTimeout(async () => {
      try {
        const replay = await getReplay(streamId)
        if (!mountedRef.current) {
          return
        }
        if (replay.mp4_status === 'ready' && saveWhenReady) {
          finish()
        } else if (replay.mp4_status === 'ready') {
          statusRef.current = 'ready'
          setState('idle')
        } else if (replay.mp4_status === 'failed') {
          fail('Conversion failed')
        } else {
          waitForFile(delayMs, saveWhenReady)
        }
      } catch {
        if (mountedRef.current) {
          fail('Cannot reach the server')
        }
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
      if (!mountedRef.current) {
        return
      }
      if (answer.state === 'ready') {
        finish()
      } else if (answer.state === 'pending') {
        statusRef.current = 'processing'
        waitForFile(answer.retryAfterMs, true)
      } else {
        fail('Conversion failed')
      }
    } catch {
      if (mountedRef.current) {
        fail('Cannot reach the server')
      }
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
