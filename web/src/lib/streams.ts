import { api } from '@/lib/api'

export type StreamStatus = 'created' | 'live' | 'ended' | 'cancelled'

export interface Stream {
  id: number
  streamer: { id: number; username: string }
  title: string
  game: string
  status: StreamStatus
  created_at: string
  started_at: string | null
  ended_at: string | null
}

export function createStream(title: string, game: string): Promise<Stream> {
  return api<Stream>('/streams', {
    method: 'POST',
    body: JSON.stringify({ title, game }),
  })
}
