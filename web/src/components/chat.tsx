import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { MAX_LENGTH, useChat } from '@/hooks/use-chat'
import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'

// how close to the bottom (px) still counts as "at the bottom"
const BOTTOM_MARGIN = 40

export function Chat({ streamId, className }: { streamId: number; className?: string }) {
  const { user } = useAuth()
  const location = useLocation()
  const { messages, error, connected, send } = useChat(streamId, user !== null)
  const [draft, setDraft] = useState('')
  const listRef = useRef<HTMLUListElement>(null)
  // false once the viewer scrolls up to read, so new messages don't pull them back down
  const atBottomRef = useRef(true)

  useEffect(() => {
    const list = listRef.current
    if (list && atBottomRef.current) {
      list.scrollTop = list.scrollHeight
    }
  }, [messages])

  function onScroll() {
    const list = listRef.current
    if (!list) {
      return
    }
    atBottomRef.current = list.scrollHeight - list.scrollTop - list.clientHeight < BOTTOM_MARGIN
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    send(draft)
    setDraft('')
    // sending a message brings you back to the bottom, like on twitch
    atBottomRef.current = true
  }

  return (
    <aside className={cn('flex h-[32rem] flex-col rounded-lg border bg-card lg:h-[calc(100svh-6rem)]', className)}>
      <p className="border-b px-3 py-2 text-center text-sm font-semibold">Chat</p>

      <ul ref={listRef} onScroll={onScroll} className="flex-1 space-y-1 overflow-y-auto px-3 py-2 text-sm">
        {messages.map((message) => (
          <li key={message.id} className="break-words">
            <span className="font-semibold text-primary">{message.author.username}</span>: {message.content}
          </li>
        ))}
      </ul>

      <div className="space-y-2 border-t p-3">
        {user ? (
          <form onSubmit={onSubmit} className="flex gap-2">
            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={MAX_LENGTH}
              placeholder="Send a message"
              disabled={!connected}
            />
            <Button type="submit" size="sm" disabled={!connected}>
              Chat
            </Button>
          </form>
        ) : (
          <p className="text-sm text-muted-foreground">
            {/* the login page sends you back here */}
            <Link to="/login" state={{ from: location.pathname }} className="text-primary hover:underline">
              Log in
            </Link>{' '}
            to chat.
          </p>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
    </aside>
  )
}
