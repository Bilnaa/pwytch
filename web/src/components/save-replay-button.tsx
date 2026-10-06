import { useEffect, useState } from 'react'
import { Bookmark as BookmarkIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { ApiError, errorMessage } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { createBookmark, deleteBookmark, findBookmark, type Bookmark } from '@/lib/bookmarks'
import type { Replay } from '@/lib/replays'
import { cn } from '@/lib/utils'

// Saves the replay in /bookmarks. The label starts as the title, it can be changed there.
// Same as FollowButton, give it key={replay.stream_id}
export function SaveReplayButton({ replay }: { replay: Replay }) {
  const { user } = useAuth()
  // undefined while we don't know yet, null when not saved
  const [saved, setSaved] = useState<Bookmark | null | undefined>(undefined)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const streamId = replay.stream_id

  useEffect(() => {
    if (!user) {
      return
    }
    let cancelled = false
    findBookmark('replay', streamId)
      .then((found) => {
        if (!cancelled) {
          setSaved(found)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [user, streamId])

  if (!user || saved === undefined) {
    return null
  }

  async function handleClick() {
    setSending(true)
    setError('')
    try {
      if (saved) {
        await deleteBookmark(saved.id)
        setSaved(null)
      } else {
        const label = replay.title ?? `Replay of ${replay.streamer_name ?? 'unknown streamer'}`
        setSaved(await createBookmark('replay', streamId, label))
      }
    } catch (err) {
      // 409: saved from another tab in the meantime
      if (err instanceof ApiError && err.status === 409) {
        setSaved(await findBookmark('replay', streamId).catch(() => null))
      } else {
        setError(errorMessage(err))
      }
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant="outline" onClick={handleClick} disabled={sending}>
        <BookmarkIcon className={cn(saved && 'fill-current')} />
        {saved ? 'Saved' : 'Save'}
      </Button>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
