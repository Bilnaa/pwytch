import { useEffect, useRef, useState } from 'react'

import { getToken, wsUrl } from '@/lib/api'

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

// Close codes sent by main on the chat WebSocket (see main/README.md)
const CLOSE_MESSAGES: Record<number, string> = {
  4401: 'Your session expired, log in again.',
  4404: 'This live does not exist.',
  1011: 'The chat is unavailable, refresh the page to try again.',
  1006: 'Cannot reach the server.',
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
    // TODO(#84, Bilnaa, 2026-10-04): load the last messages once main has GET /streams/{id}/chat/messages
    let path = `/streams/${streamId}/chat`
    const token = getToken()
    if (loggedIn && token) {
      path += `?token=${encodeURIComponent(token)}`
    }
    const socket = new WebSocket(wsUrl(path))
    socketRef.current = socket

    socket.onopen = () => {
      setConnected(true)
      setError('')
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
      if (event.code === 1000) {
        return
      }
      setError(CLOSE_MESSAGES[event.code] ?? `Chat closed (${event.code} ${event.reason})`)
    }

    return () => {
      // no error message for a close we asked for
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
