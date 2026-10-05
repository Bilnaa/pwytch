import { api } from '@/lib/api'

export interface StreamerResult {
  streamer_id: number
  streamer_name: string
  last_title: string | null
  last_game: string | null
  is_live: boolean
  live_stream_id: number | null
}

export interface MessageResult {
  message_id: string
  stream_id: number
  author_name: string
  content: string
  sent_at: string
}

export interface SearchResults {
  streamers: StreamerResult[]
  messages: MessageResult[]
}

// same minimum as main, below that it answers a 422
export const MIN_QUERY_LENGTH = 2

export function search(query: string): Promise<SearchResults> {
  return api<SearchResults>(`/search?q=${encodeURIComponent(query)}`)
}
