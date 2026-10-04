import { api, apiUrl } from '@/lib/api'

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

export interface StreamPage {
  items: Stream[]
  total: number
  page: number
  size: number
}

// The session of this streamer that is still open (created, or live and waiting
// for them to come back after a closed tab). main allows only one at a time
export async function findMyOpenStream(userId: number): Promise<Stream | null> {
  for (const status of ['live', 'created']) {
    const page = await api<StreamPage>(`/streams?status=${status}&size=100`)
    for (const stream of page.items) {
      if (stream.streamer.id === userId) {
        return stream
      }
    }
  }
  return null
}

// 100 is the max page size of main, enough for us
export async function listLives(): Promise<Stream[]> {
  const page = await api<StreamPage>('/streams?status=live&size=100')
  return page.items
}

// main can't filter /streams by streamer, so we look in the current lives
export async function findLive(username: string): Promise<Stream | null> {
  const lives = await listLives()
  for (const stream of lives) {
    // twitch urls don't care about case: /Aespa_Radio works too
    if (stream.streamer.username.toLowerCase() === username.toLowerCase()) {
      return stream
    }
  }
  return null
}

// HLS playlist of a live, relayed by main from stream
export function playlistUrl(id: number): string {
  return apiUrl(`/lives/${id}/index.m3u8`)
}
