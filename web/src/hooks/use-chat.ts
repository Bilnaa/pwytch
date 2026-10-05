import { useEffect, useRef, useState } from 'react'

import { api, getToken, wsUrl } from '@/lib/api'

export interface ChatMessage {
  id: string
  stream_id: number
  author: { id: number; username: string }
  content: string
  sent_at: string
}

// same limit as live-chat
export const MAX_LENGTH = 500

// past this, the oldest messages are dropped so a long live doesn't eat the memory
const MAX_MESSAGES = 200

const RETRY_MS = 3000

// The history comes back while the socket may already have pushed new messages,
// so both lists are put together without the doubles and sorted again
function mergeMessages(old: ChatMessage[], loaded: ChatMessage[]): ChatMessage[] {
  const byId = new Map<string, ChatMessage>()
  for (const message of [...old, ...loaded]) {
    byId.set(message.id, message)
  }
  const merged = [...byId.values()]
  // as dates: main and live-chat may not write sent_at the same way
  merged.sort((a, b) => Date.parse(a.sent_at) - Date.parse(b.sent_at))
  return merged.slice(-MAX_MESSAGES)
}

// Close codes of main where trying again won't change anything (see main/README.md).
// Any other close (main restarted, live-chat down, network lost) reconnects
const CLOSE_MESSAGES: Record<number, string> = {
  4401: 'Your session expired, log in again.',
  4404: 'This live does not exist.',
}

// live-chat sends its errors with a French detail, so we use the code
const ERROR_MESSAGES: Record<string, string> = {
  READ_ONLY: 'Log in to chat.',
  EMPTY_MESSAGE: 'Your message is empty.',
  CONTENT_TOO_LONG: `Messages are limited to ${MAX_LENGTH} characters.`,
  MESSAGE_NOT_SAVED: 'Your message was not sent, try again.',
}

// loggedIn: reconnects when it changes, so logging out from the header makes the chat read only
export function useChat(streamId: number, loggedIn: boolean) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [error, setError] = useState('')
  const [connected, setConnected] = useState(false)
  const socketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let path = `/streams/${streamId}/chat`
    const token = getToken()
    if (loggedIn && token) {
      path += `?token=${encodeURIComponent(token)}`
    }
    let socket: WebSocket
    let retry: number | undefined

    function connect() {
      socket = new WebSocket(wsUrl(path))
      socketRef.current = socket

      socket.onopen = () => {
        setConnected(true)
        setError('')
        // loaded once the socket is open, so nothing falls between the two. On a
        // reconnect it also brings back what was sent while we were away
        api<ChatMessage[]>(`/streams/${streamId}/messages`)
          .then((loaded) => setMessages((old) => mergeMessages(old, loaded)))
          .catch(() => {})
      }

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.type === 'error') {
          setError(ERROR_MESSAGES[data.code] ?? data.detail)
          return
        }
        setMessages((old) => [...old, data].slice(-MAX_MESSAGES))
      }

      socket.onclose = (event) => {
        setConnected(false)
        if (event.code in CLOSE_MESSAGES) {
          setError(CLOSE_MESSAGES[event.code])
          return
        }
        setError('Chat disconnected, reconnecting...')
        retry = window.setTimeout(connect, RETRY_MS)
      }
    }

    connect()

    return () => {
      window.clearTimeout(retry)
      // no reconnect for a close we asked for
      socket.onclose = null
      socket.close(1000)
    }
  }, [streamId, loggedIn])

  function send(content: string) {
    setError('')
    socketRef.current?.send(JSON.stringify({ content }))
  }

  return { messages, error, connected, send }
}
