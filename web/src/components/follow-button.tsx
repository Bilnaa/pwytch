import { useEffect, useState } from 'react'
import { Heart } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { ApiError, errorMessage } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { createBookmark, deleteBookmark, findFollow, notifyFollowsChanged, type Bookmark } from '@/lib/bookmarks'
import { cn } from '@/lib/utils'

interface FollowButtonProps {
  streamerId: number
  username: string
}

// Following a streamer = a bookmark of type streamer, like the heart on twitch
export function FollowButton({ streamerId, username }: FollowButtonProps) {
  const { user } = useAuth()
  // undefined while we don't know yet, null when not followed
  const [follow, setFollow] = useState<Bookmark | null | undefined>(undefined)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!user) {
      return
    }
    let cancelled = false
    findFollow(streamerId)
      .then((found) => {
        if (!cancelled) {
          setFollow(found)
        }
      })
      // the button stays hidden, the channel works without it
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [user, streamerId])

  // no following yourself
  if (!user || user.id === streamerId || follow === undefined) {
    return null
  }

  async function handleClick() {
    setSending(true)
    setError('')
    try {
      if (follow) {
        await deleteBookmark(follow.id)
        setFollow(null)
      } else {
        setFollow(await createBookmark('streamer', streamerId, username))
      }
      notifyFollowsChanged()
    } catch (err) {
      // 409: followed from another tab in the meantime, get that bookmark
      if (err instanceof ApiError && err.status === 409) {
        setFollow(await findFollow(streamerId).catch(() => null))
      } else {
        setError(errorMessage(err))
      }
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant={follow ? 'outline' : 'default'} size="sm" onClick={handleClick} disabled={sending}>
        <Heart className={cn(follow && 'fill-current')} />
        {follow ? 'Following' : 'Follow'}
      </Button>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
